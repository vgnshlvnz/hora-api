"""Restart unhealthy hora-api containers, with a cap, and keep a status file.

Docker restarts a container that exits but not one that is merely unhealthy. This sidecar polls
the Docker Engine API (over the mounted socket) for containers labelled `hora.autorestart=true`
and restarts any whose health check reports "unhealthy".

Restarting does not fix everything (a broken profiles file keeps /readyz failing), so restarts
are capped: at most WATCHER_MAX_RESTARTS per WATCHER_WINDOW seconds per container. When the cap
is reached the watcher gives up on that container ("gave_up"): it logs an error, stops
restarting it, and keeps watching until the container becomes healthy again. Everything it knows
is written to WATCHER_STATUS_FILE (JSON) on every poll, including the restart history, so a
watcher that itself restarts does not forget it already used up the cap.

Only the standard library is used. Environment:

    WATCHER_INTERVAL      seconds between polls              (default 15)
    WATCHER_MAX_RESTARTS  restarts allowed per window        (default 3)
    WATCHER_WINDOW        window length in seconds           (default 1800)
    WATCHER_LABEL         label that opts a container in     (default hora.autorestart)
    WATCHER_STATUS_FILE   status file path                   (default /status/watcher.json)
    DOCKER_SOCKET         Docker Engine socket               (default /var/run/docker.sock)

`python watcher.py --healthcheck` exits 0 if the status file is fresh and Docker was reachable.
"""

from __future__ import annotations

import http.client
import json
import os
import signal
import socket
import sys
import tempfile
import time
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class DockerError(Exception):
    pass


class _UnixConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str, timeout: float) -> None:
        super().__init__("localhost", timeout=timeout)
        self._socket_path = socket_path

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self._socket_path)
        self.sock = sock


class DockerAPI:
    """The three Engine API calls the watcher needs."""

    def __init__(self, socket_path: str, timeout: float = 10.0) -> None:
        self._socket_path = socket_path
        self._timeout = timeout

    def _request(self, method: str, path: str) -> Any:
        conn = _UnixConnection(self._socket_path, self._timeout)
        try:
            conn.request(method, path)
            response = conn.getresponse()
            raw = response.read()
        except (OSError, http.client.HTTPException) as e:
            raise DockerError(f"cannot reach Docker at {self._socket_path}: {e}") from e
        finally:
            conn.close()
        if response.status >= 300:
            raise DockerError(f"{method} {path} returned HTTP {response.status}: {raw[:200]!r}")
        return json.loads(raw) if raw else None

    def list_labelled(self, label: str) -> list[dict[str, Any]]:
        filters = urllib.parse.quote(json.dumps({"label": [f"{label}=true"]}))
        result: list[dict[str, Any]] = self._request(
            "GET", f"/containers/json?all=1&filters={filters}"
        )
        return result

    def inspect(self, container_id: str) -> dict[str, Any]:
        result: dict[str, Any] = self._request("GET", f"/containers/{container_id}/json")
        return result

    def restart(self, container_id: str, grace_seconds: int = 10) -> None:
        self._request("POST", f"/containers/{container_id}/restart?t={grace_seconds}")


@dataclass
class ServiceState:
    state: str = (
        "unknown"  # ok | starting | restarting | unhealthy | gave_up | stopped | no_healthcheck
    )
    health: str | None = None
    restarts: list[float] = field(default_factory=list)  # epoch seconds, within the window
    last_restart: float | None = None
    gave_up_at: float | None = None


def _iso(epoch: float | None) -> str | None:
    return (
        None if epoch is None else datetime.fromtimestamp(epoch, UTC).isoformat(timespec="seconds")
    )


class Watcher:
    def __init__(
        self,
        docker: DockerAPI,
        *,
        label: str = "hora.autorestart",
        max_restarts: int = 3,
        window: float = 1800.0,
        interval: float = 15.0,
        status_file: Path | None = None,
        clock: Callable[[], float] = time.time,
        log: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.docker = docker
        self.label = label
        self.max_restarts = max_restarts
        self.window = window
        self.interval = interval
        self.status_file = status_file
        self.clock = clock
        self._log = log or _log
        self.states: dict[str, ServiceState] = {}
        self.docker_error: str | None = None
        self._load_history()

    # -- one poll ------------------------------------------------------------------------

    def poll_once(self) -> None:
        now = self.clock()
        try:
            containers = self.docker.list_labelled(self.label)
            for summary in containers:
                self._check(summary["Id"], now)
            self.docker_error = None
        except DockerError as e:
            if self.docker_error != str(e):
                self._log("error", {"event": "docker_unreachable", "detail": str(e)})
            self.docker_error = str(e)
        self._write_status(now)

    def _check(self, container_id: str, now: float) -> None:
        info = self.docker.inspect(container_id)
        name = str(info["Name"]).lstrip("/")
        st = self.states.setdefault(name, ServiceState())
        st.restarts = [t for t in st.restarts if now - t < self.window]
        state = info.get("State", {})
        health = (state.get("Health") or {}).get("Status")
        st.health = health

        if not state.get("Running"):
            st.state = "stopped"  # Docker's own restart policy deals with containers that exit
        elif health is None:
            st.state = "no_healthcheck"
        elif health == "healthy":
            if st.state == "gave_up":
                self._log("info", {"event": "recovered", "container": name})
            st.state, st.gave_up_at = "ok", None
        elif health == "starting":
            if st.state not in ("gave_up", "restarting"):
                st.state = "starting"
        elif health == "unhealthy":
            self._on_unhealthy(container_id, name, st, now)

    def _on_unhealthy(self, container_id: str, name: str, st: ServiceState, now: float) -> None:
        if st.state == "gave_up":
            return  # latched until the container is seen healthy again
        if len(st.restarts) >= self.max_restarts:
            st.state, st.gave_up_at = "gave_up", now
            self._log(
                "error",
                {
                    "event": "gave_up", "container": name,
                    "detail": f"still unhealthy after {len(st.restarts)} restarts in "
                    f"{int(self.window)}s; not restarting again until it is healthy",
                },
            )  # fmt: skip
            return
        self.docker.restart(container_id)
        st.restarts.append(now)
        st.last_restart = now
        st.state = "restarting"
        self._log(
            "warning",
            {"event": "restarted", "container": name, "restarts_in_window": len(st.restarts)},
        )

    # -- status file ---------------------------------------------------------------------

    def status(self, now: float) -> dict[str, Any]:
        services = {
            name: {
                "state": st.state,
                "health": st.health,
                "restarts_in_window": len(st.restarts),
                "restart_times": [_iso(t) for t in st.restarts],
                "restart_epochs": st.restarts,
                "last_restart": _iso(st.last_restart),
                "gave_up_at": _iso(st.gave_up_at),
                "gave_up_epoch": st.gave_up_at,
            }
            for name, st in sorted(self.states.items())
        }
        return {
            "ok": self.docker_error is None
            and not any(s.state == "gave_up" for s in self.states.values()),
            "updated": _iso(now),
            "updated_epoch": now,
            "docker_error": self.docker_error,
            "policy": {
                "max_restarts": self.max_restarts,
                "window_seconds": self.window,
                "interval_seconds": self.interval,
            },
            "services": services,
        }

    def _write_status(self, now: float) -> None:
        if self.status_file is None:
            return
        try:
            self.status_file.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.status_file.parent, prefix=".watcher-")
            with os.fdopen(fd, "w") as f:
                json.dump(self.status(now), f, indent=2)
            os.replace(tmp, self.status_file)
        except OSError as e:
            self._log("error", {"event": "status_write_failed", "detail": str(e)})

    def _load_history(self) -> None:
        """Remember restarts and give-ups across a watcher restart."""
        if self.status_file is None or not self.status_file.exists():
            return
        try:
            data = json.loads(self.status_file.read_text())
            now = self.clock()
            for name, s in data.get("services", {}).items():
                st = ServiceState()
                st.restarts = [t for t in s.get("restart_epochs", []) if now - t < self.window]
                st.gave_up_at = s.get("gave_up_epoch")
                st.state = "gave_up" if st.gave_up_at else "unknown"
                st.last_restart = st.restarts[-1] if st.restarts else None
                self.states[name] = st
        except (OSError, ValueError, TypeError):
            self._log("warning", {"event": "status_history_unreadable"})


def _log(level: str, fields: dict[str, Any]) -> None:
    record = {"time": _iso(time.time()), "level": level, "service": "watcher", **fields}
    print(json.dumps(record), flush=True)


def healthcheck(status_file: Path, now: float | None = None) -> bool:
    """Fresh status file (three polls) and Docker reachable."""
    try:
        data = json.loads(status_file.read_text())
        age = (time.time() if now is None else now) - float(data["updated_epoch"])
        return data.get("docker_error") is None and age <= 3 * float(
            data["policy"]["interval_seconds"]
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


def from_env(env: dict[str, str] | None = None) -> Watcher:
    e = dict(os.environ) if env is None else env
    return Watcher(
        DockerAPI(e.get("DOCKER_SOCKET", "/var/run/docker.sock")),
        label=e.get("WATCHER_LABEL", "hora.autorestart"),
        max_restarts=int(e.get("WATCHER_MAX_RESTARTS", "3")),
        window=float(e.get("WATCHER_WINDOW", "1800")),
        interval=float(e.get("WATCHER_INTERVAL", "15")),
        status_file=Path(e.get("WATCHER_STATUS_FILE", "/status/watcher.json")),
    )


def main(argv: list[str]) -> int:
    if argv[:1] == ["--healthcheck"]:
        path = Path(os.environ.get("WATCHER_STATUS_FILE", "/status/watcher.json"))
        return 0 if healthcheck(path) else 1
    if argv:
        print(__doc__, file=sys.stderr)
        return 2
    watcher = from_env()
    stop = False

    def _stop(signum: int, frame: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    _log(
        "info",
        {
            "event": "started",
            "max_restarts": watcher.max_restarts,
            "window_seconds": watcher.window,
            "interval_seconds": watcher.interval,
        },
    )
    while not stop:
        watcher.poll_once()
        deadline = time.monotonic() + watcher.interval
        while not stop and time.monotonic() < deadline:
            time.sleep(0.5)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

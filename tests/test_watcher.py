"""deploy/watcher.py: restart logic, cap, status file, and the Docker Engine API client."""

import importlib.util
import json
import socket
import socketserver
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def w() -> ModuleType:
    spec = importlib.util.spec_from_file_location("watcher", ROOT / "deploy/watcher.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["watcher"] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    return module


class FakeDocker:
    """Stands in for DockerAPI: containers with a settable health status."""

    def __init__(self) -> None:
        self.health: dict[str, str | None] = {}
        self.running: dict[str, bool] = {}
        self.restarted: list[str] = []
        self.error: Exception | None = None

    def add(self, name: str, health: str | None = "healthy", running: bool = True) -> None:
        self.health[name], self.running[name] = health, running

    def list_labelled(self, label: str) -> list[dict[str, Any]]:
        if self.error:
            raise self.error
        return [{"Id": name} for name in self.health]

    def inspect(self, container_id: str) -> dict[str, Any]:
        health = self.health[container_id]
        state: dict[str, Any] = {"Running": self.running[container_id]}
        if health is not None:
            state["Health"] = {"Status": health}
        return {"Name": f"/{container_id}", "State": state}

    def restart(self, container_id: str, grace_seconds: int = 10) -> None:
        self.restarted.append(container_id)
        self.health[container_id] = "starting"


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


def make(
    w: ModuleType, docker: FakeDocker, tmp_path: Path, clock: Clock, **kw: Any
) -> tuple[Any, list[tuple[str, dict[str, Any]]]]:
    logs: list[tuple[str, dict[str, Any]]] = []
    watcher = w.Watcher(
        docker, status_file=tmp_path / "status.json", clock=clock,
        log=lambda level, fields: logs.append((level, fields)), **kw,
    )  # fmt: skip
    return watcher, logs


def test_healthy_containers_are_left_alone(w: ModuleType, tmp_path: Path) -> None:
    docker, clock = FakeDocker(), Clock()
    docker.add("api")
    docker.add("mcp")
    watcher, _ = make(w, docker, tmp_path, clock)
    watcher.poll_once()
    assert docker.restarted == [] and watcher.states["api"].state == "ok"
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["ok"] is True and set(status["services"]) == {"api", "mcp"}


def test_unhealthy_container_is_restarted_and_recovers(w: ModuleType, tmp_path: Path) -> None:
    docker, clock = FakeDocker(), Clock()
    docker.add("api", "unhealthy")
    watcher, logs = make(w, docker, tmp_path, clock)
    watcher.poll_once()
    assert docker.restarted == ["api"] and watcher.states["api"].state == "restarting"
    assert logs[0][1]["event"] == "restarted"
    watcher.poll_once()  # health is "starting" after the restart: no second restart
    assert docker.restarted == ["api"] and watcher.states["api"].state == "restarting"
    docker.health["api"] = "healthy"
    watcher.poll_once()
    assert watcher.states["api"].state == "ok" and docker.restarted == ["api"]


def test_starting_and_stopped_and_unchecked_containers_are_not_restarted(
    w: ModuleType, tmp_path: Path
) -> None:
    docker, clock = FakeDocker(), Clock()
    docker.add("booting", "starting")
    docker.add("exited", "unhealthy", running=False)
    docker.add("plain", None)
    watcher, _ = make(w, docker, tmp_path, clock)
    watcher.poll_once()
    assert docker.restarted == []
    assert {n: s.state for n, s in watcher.states.items()} == {
        "booting": "starting", "exited": "stopped", "plain": "no_healthcheck",
    }  # fmt: skip


def test_cap_then_gave_up_until_healthy(w: ModuleType, tmp_path: Path) -> None:
    docker, clock = FakeDocker(), Clock()
    docker.add("api", "unhealthy")
    watcher, logs = make(w, docker, tmp_path, clock, max_restarts=3, window=1800)
    for _ in range(3):  # each restart is followed by another unhealthy verdict
        watcher.poll_once()
        docker.health["api"] = "unhealthy"
        clock.now += 30
    assert docker.restarted == ["api"] * 3
    watcher.poll_once()  # fourth unhealthy verdict: cap reached
    st = watcher.states["api"]
    assert st.state == "gave_up" and docker.restarted == ["api"] * 3
    assert [f["event"] for lvl, f in logs if lvl == "error"] == ["gave_up"]
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["ok"] is False and status["services"]["api"]["state"] == "gave_up"
    assert status["services"]["api"]["restarts_in_window"] == 3

    # Latched: it stays gave_up, however long it stays unhealthy, and is not restarted.
    clock.now += 10_000
    watcher.poll_once()
    assert st.state == "gave_up" and docker.restarted == ["api"] * 3
    assert len([1 for lvl, _ in logs if lvl == "error"]) == 1  # logged once, not every poll

    docker.health["api"] = "healthy"  # someone fixed the profiles file
    watcher.poll_once()
    assert st.state == "ok" and st.gave_up_at is None
    assert logs[-1][1]["event"] == "recovered"
    assert json.loads((tmp_path / "status.json").read_text())["ok"] is True


def test_restarts_outside_the_window_do_not_count(w: ModuleType, tmp_path: Path) -> None:
    docker, clock = FakeDocker(), Clock()
    docker.add("api", "unhealthy")
    watcher, _ = make(w, docker, tmp_path, clock, max_restarts=2, window=600)
    watcher.poll_once()
    docker.health["api"] = "unhealthy"
    clock.now += 601  # the first restart has aged out
    watcher.poll_once()
    docker.health["api"] = "unhealthy"
    clock.now += 60
    watcher.poll_once()  # second restart within 600 s of the previous one only
    assert docker.restarted == ["api", "api", "api"]
    assert watcher.states["api"].state == "restarting" and len(watcher.states["api"].restarts) == 2


def test_each_container_has_its_own_budget(w: ModuleType, tmp_path: Path) -> None:
    docker, clock = FakeDocker(), Clock()
    docker.add("api", "unhealthy")
    docker.add("mcp")
    watcher, _ = make(w, docker, tmp_path, clock, max_restarts=1)
    watcher.poll_once()
    docker.health["api"] = "unhealthy"
    watcher.poll_once()
    assert watcher.states["api"].state == "gave_up" and watcher.states["mcp"].state == "ok"
    docker.health["mcp"] = "unhealthy"
    watcher.poll_once()
    assert docker.restarted == ["api", "mcp"]  # mcp still had its budget


def test_history_survives_a_watcher_restart(w: ModuleType, tmp_path: Path) -> None:
    docker, clock = FakeDocker(), Clock()
    docker.add("api", "unhealthy")
    first, _ = make(w, docker, tmp_path, clock, max_restarts=2)
    for _ in range(3):
        first.poll_once()
        docker.health["api"] = "unhealthy"
        clock.now += 30
    assert first.states["api"].state == "gave_up"

    reborn, _ = make(w, docker, tmp_path, clock, max_restarts=2)  # a fresh process, same file
    assert reborn.states["api"].state == "gave_up"
    docker.restarted.clear()
    reborn.poll_once()
    assert docker.restarted == []  # it does not start over with a full budget

    # Restarts already used count against the cap even when the watcher was not latched.
    other = FakeDocker()
    other.add("mcp", "unhealthy")
    path = tmp_path / "second.json"
    path.write_text(json.dumps({"services": {"mcp": {"restart_epochs": [clock.now - 5]}}}))
    third = w.Watcher(other, status_file=path, clock=clock, max_restarts=1, log=lambda *_: None)
    third.poll_once()
    assert other.restarted == [] and third.states["mcp"].state == "gave_up"


def test_unreadable_history_is_ignored(w: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "status.json"
    path.write_text("not json")
    watcher = w.Watcher(FakeDocker(), status_file=path, log=lambda *_: None)
    assert watcher.states == {}


def test_docker_outage_is_recorded_not_fatal(w: ModuleType, tmp_path: Path) -> None:
    docker, clock = FakeDocker(), Clock()
    docker.error = w.DockerError("cannot reach Docker")
    watcher, logs = make(w, docker, tmp_path, clock)
    watcher.poll_once()
    watcher.poll_once()
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["ok"] is False and status["docker_error"] == "cannot reach Docker"
    assert len(logs) == 1  # reported once
    docker.error = None
    watcher.poll_once()
    assert json.loads((tmp_path / "status.json").read_text())["docker_error"] is None


def test_healthcheck_needs_a_fresh_status_without_docker_errors(
    w: ModuleType, tmp_path: Path
) -> None:
    docker, clock = FakeDocker(), Clock()
    watcher, _ = make(w, docker, tmp_path, clock, interval=15)
    path = tmp_path / "status.json"
    assert w.healthcheck(path, now=clock.now) is False  # nothing written yet
    watcher.poll_once()
    assert w.healthcheck(path, now=clock.now + 44) is True
    assert w.healthcheck(path, now=clock.now + 46) is False  # older than three intervals
    docker.error = w.DockerError("down")
    watcher.poll_once()
    assert w.healthcheck(path, now=clock.now) is False
    path.write_text("{}")
    assert w.healthcheck(path) is False


def test_status_file_is_written_atomically_to_a_new_directory(
    w: ModuleType, tmp_path: Path
) -> None:
    docker, clock = FakeDocker(), Clock()
    docker.add("api")
    path = tmp_path / "new" / "dir" / "watcher.json"
    watcher = w.Watcher(docker, status_file=path, clock=clock, log=lambda *_: None)
    watcher.poll_once()
    assert json.loads(path.read_text())["services"]["api"]["state"] == "ok"
    assert [p.name for p in path.parent.iterdir()] == ["watcher.json"]  # no temp files left


# ---------------------------------------------------------------------------
# The Docker Engine API client, against a fake engine on a unix socket
# ---------------------------------------------------------------------------


class Engine:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str]] = []
        self.containers = [{"Id": "abc123"}]
        self.fail_restart = False


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[tuple[str, Engine]]:
    state = Engine()

    class Handler(BaseHTTPRequestHandler):
        def _reply(self, status: int, body: object = None) -> None:
            payload = b"" if body is None else json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            state.requests.append(("GET", self.path))
            if self.path.startswith("/containers/json"):
                self._reply(200, state.containers)
            elif self.path == "/containers/abc123/json":
                self._reply(200, {"Name": "/hora-api-api-1", "State": {"Running": True}})
            else:
                self._reply(404, {"message": "no such container"})

        def do_POST(self) -> None:
            state.requests.append(("POST", self.path))
            self._reply(500 if state.fail_restart else 204)

        def log_message(self, *args: object) -> None:
            pass

        def address_string(self) -> str:
            return "unix"

    class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
        daemon_threads = True

        def get_request(self) -> tuple[socket.socket, Any]:
            request, _ = super().get_request()
            return request, ("unix", 0)

    path = str(tmp_path / "docker.sock")
    server = Server(path, Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield path, state
    server.shutdown()
    server.server_close()


def test_client_lists_by_label_inspects_and_restarts(
    w: ModuleType, engine: tuple[str, Engine]
) -> None:
    path, state = engine
    api = w.DockerAPI(path)
    assert api.list_labelled("hora.autorestart") == [{"Id": "abc123"}]
    method, target = state.requests[0]
    assert method == "GET" and "hora.autorestart%3Dtrue" in target and "all=1" in target
    assert api.inspect("abc123")["Name"] == "/hora-api-api-1"
    api.restart("abc123", grace_seconds=5)
    assert state.requests[-1] == ("POST", "/containers/abc123/restart?t=5")


def test_client_errors_become_docker_errors(w: ModuleType, engine: tuple[str, Engine]) -> None:
    path, state = engine
    api = w.DockerAPI(path)
    with pytest.raises(w.DockerError, match="HTTP 404"):
        api.inspect("missing")
    state.fail_restart = True
    with pytest.raises(w.DockerError, match="HTTP 500"):
        api.restart("abc123")
    with pytest.raises(w.DockerError, match="cannot reach Docker"):
        w.DockerAPI("/nonexistent/docker.sock").list_labelled("x")


def test_watcher_end_to_end_against_the_fake_engine(
    w: ModuleType, engine: tuple[str, Engine], tmp_path: Path
) -> None:
    path, state = engine
    # An unhealthy container behind the real client and the real socket protocol.
    api = w.DockerAPI(path)

    class Unhealthy:
        def list_labelled(self, label: str) -> list[dict[str, Any]]:
            result: list[dict[str, Any]] = api.list_labelled(label)
            return result

        def inspect(self, container_id: str) -> dict[str, Any]:
            info: dict[str, Any] = api.inspect(container_id)
            info["State"]["Health"] = {"Status": "unhealthy"}
            return info

        def restart(self, container_id: str, grace_seconds: int = 10) -> None:
            api.restart(container_id, grace_seconds)

    watcher = w.Watcher(
        Unhealthy(), status_file=tmp_path / "s.json", log=lambda *_: None, max_restarts=1
    )
    watcher.poll_once()
    assert ("POST", "/containers/abc123/restart?t=10") in state.requests
    watcher.poll_once()
    assert watcher.states["hora-api-api-1"].state == "gave_up"


def test_main_argument_handling(
    w: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert w.main(["--nope"]) == 2
    monkeypatch.setenv("WATCHER_STATUS_FILE", str(tmp_path / "absent.json"))
    assert w.main(["--healthcheck"]) == 1
    watcher = w.from_env(
        {"WATCHER_MAX_RESTARTS": "5", "WATCHER_WINDOW": "60", "WATCHER_INTERVAL": "2",
         "WATCHER_LABEL": "x.y", "WATCHER_STATUS_FILE": str(tmp_path / "s.json")}
    )  # fmt: skip
    assert (watcher.max_restarts, watcher.window, watcher.interval, watcher.label) == (
        5,
        60,
        2,
        "x.y",
    )
    assert w.from_env({}).max_restarts == 3

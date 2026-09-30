"""Deployment files: structure, consistency with the code's settings, and the health probe."""

import importlib.util
import re
import subprocess
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import ModuleType

import pytest
import yaml

from hora_api.api.settings import ApiSettings
from hora_api.scoring.settings import ScoringSettings

ROOT = Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy"


def parse_env_example(path: Path) -> dict[str, str]:
    pairs = (
        line.split("=", 1)
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    return {k.strip(): v.strip() for k, v in pairs}


def load_unit(path: Path) -> dict[str, list[str]]:
    """A systemd unit as {'Section.Key': [values...]}; keys may repeat."""
    lines = [ln for ln in path.read_text().splitlines() if not ln.lstrip().startswith("#")]
    out: dict[str, list[str]] = {}
    section = ""
    for line in lines:
        m = re.match(r"\[(\w+)]", line)
        if m:
            section = m.group(1)
        elif "=" in line:
            key, value = line.split("=", 1)
            out.setdefault(f"{section}.{key.strip()}", []).append(value.strip())
    return out


# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------


def test_compose_services() -> None:
    compose = yaml.safe_load((DEPLOY / "docker-compose.yml").read_text())
    api, mcp = compose["services"]["api"], compose["services"]["mcp"]
    dockerfile = (DEPLOY / "Dockerfile").read_text()
    for svc, target in ((api, "api"), (mcp, "mcp")):
        assert svc["build"]["target"] == target
        assert re.search(rf"^FROM \S+ AS {target}$", dockerfile, re.M)
        assert svc["restart"] == "unless-stopped"
        assert svc["healthcheck"]["test"][:3] == ["CMD", "python", "/app/healthcheck.py"]
    assert mcp["depends_on"]["api"]["condition"] == "service_healthy"
    assert mcp["environment"]["HORA_API_URL"] == "http://api:8000"
    # Profiles are mounted read-only from outside the repo.
    (volume,) = api["volumes"]
    assert volume.endswith(":/profiles:ro") and "PROFILES_DIR" in volume


def test_compose_requires_credentials_and_holds_no_secrets() -> None:
    text = (DEPLOY / "docker-compose.yml").read_text()
    for var in ("API_KEYS", "HORA_API_KEY", "HORA_MCP_TOKEN", "PROFILES_DIR"):
        assert f"${{{var}:?" in text, f"{var} must be mandatory"
    compose = yaml.safe_load(text)
    for svc in compose["services"].values():
        for value in svc["environment"].values():
            assert str(value).startswith("${") or str(value).startswith("http://api")
            assert "change-me" not in str(value)


def test_dockerfile_installs_locked_runtime_deps_as_non_root() -> None:
    text = (DEPLOY / "Dockerfile").read_text()
    assert text.count("uv sync --frozen --no-dev") == 2
    assert (
        text.count("USER hora") == 3 and text.count("--uid 10001") == 2
    )  # base (api, mcp) and watcher
    assert "DATA_DIR=/app/data" in text and "COPY data ./data" in text
    assert "COPY deploy/healthcheck.py" in text


def test_dockerignore_keeps_secrets_and_junk_out() -> None:
    entries = (ROOT / ".dockerignore").read_text().split()
    for must in (".git", ".venv", "deploy/.env", "*.bundle"):
        assert must in entries


def test_deploy_env_is_git_ignored() -> None:
    result = subprocess.run(
        ["git", "check-ignore", "-q", "deploy/.env"], cwd=ROOT, capture_output=True
    )
    assert result.returncode == 0


def known_variables() -> set[str]:
    api = {name.upper() for name in ApiSettings.model_fields}
    scoring = {f"HORA_SCORING_{name.upper()}" for name in ScoringSettings.model_fields}
    mcp_source = (ROOT / "mcp-server/src/hora_mcp/settings.py").read_text()
    mcp = set(re.findall(r'e\.get\("([A-Z_]+)"', mcp_source))
    compose_only = {
        "PROFILES_DIR", "API_PUBLISH", "MCP_PUBLISH", "DOCKER_GID", "WATCHER_STATUS_DIR",
        "WATCHER_INTERVAL", "WATCHER_MAX_RESTARTS", "WATCHER_WINDOW",
    }  # fmt: skip
    systemd_only = {"HORA_BIND", "HORA_PORT"}
    return api | scoring | mcp | compose_only | systemd_only


@pytest.mark.parametrize(
    "path",
    [
        DEPLOY / "env.example",
        DEPLOY / "systemd/hora-api.env.example",
        DEPLOY / "systemd/hora-mcp.env.example",
    ],
)
def test_env_examples_only_use_variables_the_code_reads(path: Path) -> None:
    variables = parse_env_example(path)
    assert variables
    assert set(variables) <= known_variables(), set(variables) - known_variables()
    # Uncommented secret placeholders must be obviously placeholders.
    for name, value in variables.items():
        if any(s in name for s in ("KEY", "TOKEN")):
            assert value.startswith("change-me")


def test_compose_env_example_covers_the_required_variables() -> None:
    variables = parse_env_example(DEPLOY / "env.example")
    required = {"PROFILES_DIR", "API_KEYS", "HORA_API_KEY", "HORA_MCP_TOKEN", "DOCKER_GID"}
    assert required <= set(variables)


def test_watcher_service_is_opt_in_capped_and_locked_down() -> None:
    compose = yaml.safe_load((DEPLOY / "docker-compose.yml").read_text())
    services = compose["services"]
    # Only labelled services are watched, and only the two app services carry the label.
    assert services["api"]["labels"] == {"hora.autorestart": "true"}
    assert services["mcp"]["labels"] == {"hora.autorestart": "true"}
    assert "labels" not in services["watcher"]

    watcher = services["watcher"]
    assert watcher["build"]["target"] == "watcher" and watcher["restart"] == "unless-stopped"
    assert watcher["user"] == "10001:10001" and watcher["read_only"] is True
    assert watcher["cap_drop"] == ["ALL"] and "no-new-privileges:true" in watcher["security_opt"]
    assert watcher["group_add"] == ["${DOCKER_GID:?set DOCKER_GID in deploy/.env}"]
    assert "/var/run/docker.sock:/var/run/docker.sock" in watcher["volumes"]
    assert any(v.endswith(":/status") for v in watcher["volumes"])
    env = watcher["environment"]
    assert env["WATCHER_MAX_RESTARTS"] == "${WATCHER_MAX_RESTARTS:-3}"
    assert env["WATCHER_WINDOW"] == "${WATCHER_WINDOW:-1800}"
    assert watcher["healthcheck"]["test"][-1] == "--healthcheck"

    dockerfile = (DEPLOY / "Dockerfile").read_text()
    stage = dockerfile[dockerfile.index("AS watcher") :]
    assert "uv" not in stage and "COPY deploy/watcher.py" in stage  # stdlib only

    # Nothing else may mount the Docker socket.
    assert not any(
        "docker.sock" in str(v)
        for name, svc in services.items()
        if name != "watcher"
        for v in svc.get("volumes", [])
    )


def test_watcher_status_dir_is_git_ignored() -> None:
    result = subprocess.run(
        ["git", "check-ignore", "-q", "deploy/watcher-status/watcher.json"],
        cwd=ROOT,
        capture_output=True,
    )
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# systemd
# ---------------------------------------------------------------------------


def test_service_units() -> None:
    api = load_unit(DEPLOY / "systemd/hora-api.service")
    mcp = load_unit(DEPLOY / "systemd/hora-mcp.service")
    assert api["Service.EnvironmentFile"] == ["/etc/hora-api/hora-api.env"]
    assert "hora_api.api.app:app" in api["Service.ExecStart"][0]
    assert "${HORA_BIND}" in api["Service.ExecStart"][0]
    assert {"HORA_BIND=0.0.0.0", "HORA_PORT=8000"} <= set(api["Service.Environment"])
    assert mcp["Service.EnvironmentFile"] == ["/etc/hora-api/hora-mcp.env"]
    assert mcp["Service.ExecStart"] == ["/opt/hora-api/mcp-server/.venv/bin/hora-mcp"]
    assert "hora-api.service" in mcp["Unit.After"][0]
    for unit in (api, mcp):
        assert unit["Service.User"] == ["hora"] and unit["Service.Restart"] == ["on-failure"]
        assert unit["Service.NoNewPrivileges"] == ["yes"]
        assert unit["Service.ProtectSystem"] == ["strict"]
        assert unit["Install.WantedBy"] == ["multi-user.target"]


def test_healthcheck_unit_and_timer() -> None:
    service = load_unit(DEPLOY / "systemd/hora-healthcheck.service")
    timer = load_unit(DEPLOY / "systemd/hora-healthcheck.timer")
    assert service["Service.Type"] == ["oneshot"]
    command = service["Service.ExecStart"][0]
    assert "/readyz" in command and "systemctl restart hora-api.service" in command
    assert timer["Timer.OnUnitActiveSec"] == ["1min"]
    assert timer["Install.WantedBy"] == ["timers.target"]


# ---------------------------------------------------------------------------
# Scripts
# ---------------------------------------------------------------------------


def test_smoke_script_is_valid_bash_and_executable() -> None:
    script = ROOT / "scripts/smoke.sh"
    assert script.stat().st_mode & 0o111
    assert subprocess.run(["bash", "-n", str(script)]).returncode == 0


# ---------------------------------------------------------------------------
# Health probe
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def probe() -> ModuleType:
    spec = importlib.util.spec_from_file_location("healthcheck", DEPLOY / "healthcheck.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def server() -> Iterator[tuple[int, dict[str, int]]]:
    """A local HTTP server whose reply status can be changed by the test."""
    state = {"status": 200}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(state["status"])
            self.end_headers()

        def log_message(self, *args: object) -> None:
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd.server_address[1], state
    httpd.shutdown()


def test_api_probe_needs_a_200(probe: ModuleType, server: tuple[int, dict[str, int]]) -> None:
    port, state = server
    assert probe.check("api", port) is True
    state["status"] = 503  # not ready: unhealthy
    assert probe.check("api", port) is False


def test_mcp_probe_accepts_any_http_answer(
    probe: ModuleType, server: tuple[int, dict[str, int]]
) -> None:
    port, state = server
    for status in (200, 401, 405):
        state["status"] = status
        assert probe.check("mcp", port) is True


def test_probe_fails_when_nothing_listens(probe: ModuleType) -> None:
    assert probe.check("api", 9) is False and probe.check("mcp", 9) is False
    assert probe.main([]) == 2 and probe.main(["nope"]) == 2
    assert probe.main(["api", "9"]) == 1

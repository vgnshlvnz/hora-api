import pytest


@pytest.fixture(autouse=True)
def _no_real_keys_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Never read the developer's real ~/.config/hora-api/keys.yaml (it would switch auth on)."""
    monkeypatch.setenv("KEYS_PATH", str(tmp_path_factory.mktemp("nokeys") / "keys.yaml"))

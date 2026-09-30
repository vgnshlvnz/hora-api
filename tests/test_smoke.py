import importlib

import pytest

import hora_api


@pytest.mark.parametrize("name", ["core", "scoring", "api", "data"])
def test_subpackages_import(name: str) -> None:
    importlib.import_module(f"hora_api.{name}")


def test_version() -> None:
    assert hora_api.__version__ == "0.4.0"

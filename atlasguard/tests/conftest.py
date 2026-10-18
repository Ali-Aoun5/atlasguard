import os
import pytest

os.environ["AG_OFFLINE"] = "1"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("AG_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("AG_OFFLINE", "1")
    from atlasguard.sandbox.db import init_db
    init_db(reset=True)

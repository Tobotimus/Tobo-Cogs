import tempfile

import py
import pytest
from _pytest.monkeypatch import MonkeyPatch
import redbot.core.data_manager


@pytest.fixture(scope="session")
def monkeysession(request):
    mp = MonkeyPatch()
    request.addfinalizer(mp.undo)
    return mp


@pytest.fixture(scope="session")
def tmp_config(request):
    tmpdir = py.path.local(tempfile.mkdtemp())
    request.addfinalizer(lambda: tmpdir.remove(rec=1))
    ret = redbot.core.data_manager.basic_config_default.copy()
    ret["DATA_PATH"] = str(tmpdir)
    return ret


@pytest.fixture(scope="session", autouse=True)
def tmp_data_dir(monkeysession, tmp_config):
    monkeysession.setattr(redbot.core.data_manager, "basic_config", tmp_config)

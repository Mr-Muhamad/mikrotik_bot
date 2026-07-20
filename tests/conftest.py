"""Central test fixtures for all test modules."""

import os
import tempfile
from unittest.mock import patch

import pytest

from tests.fixtures.telegram_mocks import make_mock_update, make_mock_context
from tests.mocks.mikrotik_api_mock import MikrotikAPIMock


@pytest.fixture(autouse=True)
def temp_db():
    """Replace DB_PATH with a temp file and init tables before each test.

    This prevents integration tests from writing to the production database.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp_path = f.name
    with patch("database.models.DB_PATH", tmp_path), patch(
        "database.models.os.path.dirname", return_value=os.path.dirname(tmp_path)
    ):
        from database.models import init_db

        init_db()
        yield
    import gc

    gc.collect()
    try:
        os.unlink(tmp_path)
    except PermissionError:
        pass


@pytest.fixture
def mock_update():
    """Basic mock Update — user typed no text, no callback."""
    return make_mock_update(text="")


@pytest.fixture
def mock_context():
    """Mock Context with clean user_data and bot_data."""
    return make_mock_context()


@pytest.fixture
def mock_mikrotik_api():
    """Patch the singleton mikrotik_api with an in-memory mock.

    Patches all modules that import `mikrotik_api` at module level
    (since `from core.mikrotik_api import mikrotik_api` creates local refs).
    """
    mock = MikrotikAPIMock()
    from core.hotspot_manager import hotspot_manager

    hotspot_manager._users_cache.clear()
    with patch("core.mikrotik_api.mikrotik_api", mock), patch(
        "core.hotspot_manager.mikrotik_api", mock
    ), patch("core.backup.system.mikrotik_api", mock), patch(
        "core.backup.userman.mikrotik_api", mock
    ), patch(
        "core.backup.restore.mikrotik_api", mock
    ), patch(
        "bot.handlers.router_flows.discovery.mikrotik_api", mock
    ), patch(
        "bot.handlers.router_flows.saved.mikrotik_api", mock
    ), patch(
        "bot.handlers.router_flows.rename.mikrotik_api", mock
    ), patch(
        "bot.handlers.router_flows.reboot.mikrotik_api", mock
    ), patch(
        "bot.handlers.common.mikrotik_api", mock
    ), patch(
        "bot.handlers.commands_basic.mikrotik_api", mock
    ), patch(
        "bot.handlers.router_system.mikrotik_api", mock
    ), patch(
        "bot.handlers.stats.mikrotik_api", mock
    ), patch(
        "core.stats.mikrotik_api", mock
    ), patch(
        "core.userman_manager.mikrotik_api", mock
    ), patch(
        "core.profile_sync.mikrotik_api", mock
    ):
        yield mock


@pytest.fixture
def mock_config():
    """Ensure config values are available during tests."""
    with patch("config.ADMIN_IDS", [724730774]):
        with patch("config.ROUTER_KEY_PREFIX", "discovered_"):
            yield

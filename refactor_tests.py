import sys

def refactor_test_hotspot_add_handler():
    with open("tests/bot/handlers/test_hotspot_add_handler.py", "r", encoding="utf-8") as f:
        content = f.read()

    if "get_hotspot_add_session" not in content:
        content = content.replace("from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update",
                                  "from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update\nfrom bot.handlers.session_models import get_hotspot_add_session")

    content = content.replace('c.user_data["add_username"]', 'get_hotspot_add_session(c.user_data).username')
    content = content.replace('c.user_data["add_password"]', 'get_hotspot_add_session(c.user_data).password')
    content = content.replace('c.user_data["add_profile"]', 'get_hotspot_add_session(c.user_data).profile')
    content = content.replace('c.user_data["add_bytes"]', 'get_hotspot_add_session(c.user_data).bytes_total')
    content = content.replace('c.user_data["add_uptime"]', 'get_hotspot_add_session(c.user_data).uptime_value')
    content = content.replace('c.user_data["uptime_unit"]', 'get_hotspot_add_session(c.user_data).uptime_type')

    with open("tests/bot/handlers/test_hotspot_add_handler.py", "w", encoding="utf-8") as f:
        f.write(content)

def refactor_test_hotspot_common():
    with open("tests/bot/handlers/test_hotspot_common.py", "r", encoding="utf-8") as f:
        content = f.read()

    if "get_hotspot_add_session" not in content:
        content = content.replace("from tests.fixtures.telegram_mocks import make_mock_context as _ctx",
                                  "from tests.fixtures.telegram_mocks import make_mock_context as _ctx\nfrom bot.handlers.session_models import get_hotspot_add_session")

    content = content.replace('ctx.user_data["add_username"] = "u1"', 'get_hotspot_add_session(ctx.user_data).username = "u1"')
    content = content.replace('ctx.user_data["add_password"] = "p1"', 'get_hotspot_add_session(ctx.user_data).password = "p1"')
    content = content.replace('ctx.user_data["add_profile"] = "1M"', 'get_hotspot_add_session(ctx.user_data).profile = "1M"')
    content = content.replace('ctx.user_data["add_bytes"] = "1G"', 'get_hotspot_add_session(ctx.user_data).bytes_total = "1G"')
    content = content.replace('ctx.user_data["add_uptime"] = "1d"', 'get_hotspot_add_session(ctx.user_data).uptime_value = "1d"')
    content = content.replace('ctx.user_data["uptime_unit"] = "d"', 'get_hotspot_add_session(ctx.user_data).uptime_type = "d"')
    
    content = content.replace('assert "add_username" not in ctx.user_data', 'assert "hotspot_add_session" not in ctx.user_data')

    with open("tests/bot/handlers/test_hotspot_common.py", "w", encoding="utf-8") as f:
        f.write(content)

refactor_test_hotspot_add_handler()
refactor_test_hotspot_common()
print("Done refactoring tests")

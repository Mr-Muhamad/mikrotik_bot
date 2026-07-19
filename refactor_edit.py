import sys
import os

def refactor_hotspot_edit():
    with open("bot/handlers/hotspot_edit.py", "r", encoding="utf-8") as f:
        content = f.read()

    if "get_hotspot_edit_session" not in content:
        content = content.replace("from bot.handlers.handler_utils import make_back_step",
                                  "from bot.handlers.handler_utils import make_back_step\nfrom .session_models import get_hotspot_edit_session")

    # context.user_data["edit_user_id"]
    content = content.replace('context.user_data.get("edit_user_id")', 'get_hotspot_edit_session(context.user_data).user_id')
    content = content.replace('context.user_data["edit_user_id"]', 'get_hotspot_edit_session(context.user_data).user_id')
    
    # context.user_data["edit_user_data"]
    content = content.replace('context.user_data.get("edit_user_data", {})', 'get_hotspot_edit_session(context.user_data).user_data')
    content = content.replace('context.user_data.get("edit_user_data")', 'get_hotspot_edit_session(context.user_data).user_data')
    content = content.replace('context.user_data["edit_user_data"]', 'get_hotspot_edit_session(context.user_data).user_data')
    
    # context.user_data["edit_field"]
    content = content.replace('context.user_data.get("edit_field")', 'get_hotspot_edit_session(context.user_data).current_field')
    content = content.replace('context.user_data["edit_field"]', 'get_hotspot_edit_session(context.user_data).current_field')

    with open("bot/handlers/hotspot_edit.py", "w", encoding="utf-8") as f:
        f.write(content)

def refactor_hotspot_common():
    with open("bot/handlers/hotspot_common.py", "r", encoding="utf-8") as f:
        content = f.read()

    if "get_hotspot_edit_session" not in content:
        content = content.replace("from .session_models import get_hotspot_add_session",
                                  "from .session_models import get_hotspot_add_session, get_hotspot_edit_session")

    content = content.replace('context.user_data["edit_user_id"] = user.get(".id", "")', 'get_hotspot_edit_session(context.user_data).user_id = user.get(".id", "")')
    content = content.replace('context.user_data["edit_user_data"] = user', 'get_hotspot_edit_session(context.user_data).user_data = user')

    with open("bot/handlers/hotspot_common.py", "w", encoding="utf-8") as f:
        f.write(content)

def refactor_tests():
    test_file = "tests/bot/handlers/test_hotspot_edit_handler.py"
    if not os.path.exists(test_file):
        return

    with open(test_file, "r", encoding="utf-8") as f:
        content = f.read()

    if "get_hotspot_edit_session" not in content:
        content = content.replace("from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update",
                                  "from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update\nfrom bot.handlers.session_models import get_hotspot_edit_session")

    content = content.replace('c.user_data["edit_user_id"]', 'get_hotspot_edit_session(c.user_data).user_id')
    content = content.replace('c.user_data["edit_user_data"]', 'get_hotspot_edit_session(c.user_data).user_data')
    content = content.replace('c.user_data["edit_field"]', 'get_hotspot_edit_session(c.user_data).current_field')
    
    # same for ctx if any
    content = content.replace('ctx.user_data["edit_user_id"]', 'get_hotspot_edit_session(ctx.user_data).user_id')
    content = content.replace('ctx.user_data["edit_user_data"]', 'get_hotspot_edit_session(ctx.user_data).user_data')

    with open(test_file, "w", encoding="utf-8") as f:
        f.write(content)

refactor_hotspot_edit()
refactor_hotspot_common()
refactor_tests()
print("Done")

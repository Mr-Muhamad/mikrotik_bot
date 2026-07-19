import sys
import os

def refactor_integration_tests():
    test_file = "tests/integration/test_hotspot_edit_flow.py"
    if not os.path.exists(test_file):
        print("Not found")
        return

    with open(test_file, "r", encoding="utf-8") as f:
        content = f.read()

    if "get_hotspot_edit_session" not in content:
        content = content.replace("from tests.fixtures.telegram_mocks import make_mock_update",
                                  "from tests.fixtures.telegram_mocks import make_mock_update\nfrom bot.handlers.session_models import get_hotspot_edit_session")

    content = content.replace('context.user_data["edit_user_id"]', 'get_hotspot_edit_session(context.user_data).user_id')
    content = content.replace('context.user_data["edit_user_data"]', 'get_hotspot_edit_session(context.user_data).user_data')
    content = content.replace('context.user_data["edit_field"]', 'get_hotspot_edit_session(context.user_data).current_field')
    
    # same for ctx if any
    content = content.replace('ctx.user_data["edit_user_id"]', 'get_hotspot_edit_session(ctx.user_data).user_id')
    content = content.replace('ctx.user_data["edit_user_data"]', 'get_hotspot_edit_session(ctx.user_data).user_data')

    with open(test_file, "w", encoding="utf-8") as f:
        f.write(content)

refactor_integration_tests()
print("Done integration tests")

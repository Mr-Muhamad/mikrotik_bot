import os

def fix_imports_and_syntax():
    # 1. hotspot_add.py
    with open("bot/handlers/hotspot_add.py", "r", encoding="utf-8") as f:
        content = f.read()
    if "HOTSPOT_ADD_BYTES_HINT" not in content[:1000]:
        content = content.replace("from bot.messages import (", "from bot.messages import (\n    HOTSPOT_ADD_BYTES_HINT,\n    HOTSPOT_ADD_INVALID_UPTIME,\n    HOTSPOT_ADD_USE_BUTTONS,")
    with open("bot/handlers/hotspot_add.py", "w", encoding="utf-8") as f:
        f.write(content)

    # 2. hotspot_common.py
    with open("bot/handlers/hotspot_common.py", "r", encoding="utf-8") as f:
        content = f.read()
    if "HOTSPOT_PAGINATION_DELETE" not in content[:1000]:
        content = content.replace("from bot.messages import CONFIRM_DELETE, NO_RESULTS", "from bot.messages import CONFIRM_DELETE, NO_RESULTS, HOTSPOT_PAGINATION_DELETE, HOTSPOT_PAGINATION_EDIT")
    with open("bot/handlers/hotspot_common.py", "w", encoding="utf-8") as f:
        f.write(content)

    # 3. hotspot_edit.py
    with open("bot/handlers/hotspot_edit.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    # Fix syntax error
    bad_syntax = """        HOTSPOT_EDIT_FIELD_PROMPT.format(field_name=field_names.get(field, field))
        HOTSPOT_EDIT_CURRENT_VALUE.format(current_value=current_value),"""
    good_syntax = """        HOTSPOT_EDIT_FIELD_PROMPT.format(field_name=field_names.get(field, field)) +
        HOTSPOT_EDIT_CURRENT_VALUE.format(current_value=current_value),"""
    content = content.replace(bad_syntax, good_syntax)

    if "HOTSPOT_EDIT_RESET_SUCCESS" not in content[:1000]:
        content = content.replace("from bot.messages import (", "from bot.messages import (\n    HOTSPOT_EDIT_RESET_SUCCESS,\n    HOTSPOT_EDIT_KICK_COUNT,\n    HOTSPOT_EDIT_KICK_COUNT_INLINE,\n    HOTSPOT_EDIT_SUCCESS,\n    HOTSPOT_EDIT_FIELD_PROMPT,\n    HOTSPOT_EDIT_CURRENT_VALUE,\n    HOTSPOT_EDIT_EMPTY_VALUE,")
    with open("bot/handlers/hotspot_edit.py", "w", encoding="utf-8") as f:
        f.write(content)

    # 4. hotspot_search.py
    with open("bot/handlers/hotspot_search.py", "r", encoding="utf-8") as f:
        content = f.read()
    if "HOTSPOT_SEARCH_OFFLINE" not in content[:1000]:
        content = content.replace("from bot.messages import (", "from bot.messages import (\n    HOTSPOT_SEARCH_OFFLINE,\n    HOTSPOT_SEARCH_FOUND,\n    HOTSPOT_SEARCH_LIMIT,\n    HOTSPOT_KICK_SUCCESS_SINGLE,\n    HOTSPOT_INVALID_BLOCK_DATA,\n    HOTSPOT_INVALID_UNBLOCK_DATA,")
    with open("bot/handlers/hotspot_search.py", "w", encoding="utf-8") as f:
        f.write(content)

fix_imports_and_syntax()
print("Fixed")

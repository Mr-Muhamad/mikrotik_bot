import sys
import re

def refactor_hotspot_add():
    with open("bot/handlers/hotspot_add.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Add import
    if "get_hotspot_add_session" not in content:
        content = content.replace("from .hotspot_common import execute_add_user",
                                  "from .hotspot_common import execute_add_user\nfrom .session_models import get_hotspot_add_session")

    # Replace user_data assignments
    content = content.replace('context.user_data["add_username"] = username',
                              'get_hotspot_add_session(context.user_data).username = username')
    content = content.replace('context.user_data["add_password"] = password',
                              'get_hotspot_add_session(context.user_data).password = password')
    content = content.replace('context.user_data["add_profile"] = profile',
                              'get_hotspot_add_session(context.user_data).profile = profile')
    content = content.replace('context.user_data["add_bytes"] = validate_bytes_input(bytes_input)',
                              'get_hotspot_add_session(context.user_data).bytes_total = validate_bytes_input(bytes_input)')
    content = content.replace('context.user_data["add_password"] = ""',
                              'get_hotspot_add_session(context.user_data).password = ""')
    content = content.replace('context.user_data["add_bytes"] = ""',
                              'get_hotspot_add_session(context.user_data).bytes_total = ""')
    content = content.replace('context.user_data["add_uptime"] = ""',
                              'get_hotspot_add_session(context.user_data).uptime_value = ""')
    content = content.replace('context.user_data["add_uptime"] = uptime',
                              'get_hotspot_add_session(context.user_data).uptime_value = str(uptime)')
    
    # uptime unit
    content = content.replace('prompt, _ = set_uptime_unit(context.user_data, "uptime_unit", "hours")',
                              'prompt, _ = set_uptime_unit(None, "uptime_unit", "hours")\n        get_hotspot_add_session(context.user_data).uptime_type = "hours"')
    content = content.replace('prompt, _ = set_uptime_unit(context.user_data, "uptime_unit", "days")',
                              'prompt, _ = set_uptime_unit(None, "uptime_unit", "days")\n        get_hotspot_add_session(context.user_data).uptime_type = "days"')
    content = content.replace('unit = context.user_data.get("uptime_unit", "hours")',
                              'unit = get_hotspot_add_session(context.user_data).uptime_type or "hours"')

    with open("bot/handlers/hotspot_add.py", "w", encoding="utf-8") as f:
        f.write(content)

def refactor_hotspot_common():
    with open("bot/handlers/hotspot_common.py", "r", encoding="utf-8") as f:
        content = f.read()

    if "get_hotspot_add_session" not in content:
        content = content.replace("from utils.pagination import Paginator",
                                  "from utils.pagination import Paginator\nfrom .session_models import get_hotspot_add_session")

    old_func = '''async def execute_add_user(context, user_id, router_key, comment):
    try:
        await run_blocking(
            hotspot_manager.add_user,
            router_key=router_key,
            name=context.user_data["add_username"],
            password=context.user_data.get("add_password", ""),
            profile=context.user_data["add_profile"],
            bytes_total=context.user_data.get("add_bytes", ""),
            uptime=context.user_data.get("add_uptime", ""),
            comment=comment,
        )
        await run_blocking(
            log_action,
            "add_user",
            context.user_data["add_username"],
            router_key,
            user_id,
        )
        return True, None
    except Exception as e:
        logger.exception(f"execute_add_user failed: {e}")
        if "already have user" in str(e):
            for k in [
                "add_username",
                "add_password",
                "add_profile",
                "add_bytes",
                "add_uptime",
                "uptime_unit",
            ]:
                context.user_data.pop(k, None)
            return False, "duplicate"
        return False, str(e)'''

    new_func = '''async def execute_add_user(context, user_id, router_key, comment):
    session = get_hotspot_add_session(context.user_data)
    try:
        await run_blocking(
            hotspot_manager.add_user,
            router_key=router_key,
            name=session.username,
            password=session.password,
            profile=session.profile,
            bytes_total=session.bytes_total,
            uptime=session.uptime_value,
            comment=comment,
        )
        await run_blocking(
            log_action,
            "add_user",
            session.username,
            router_key,
            user_id,
        )
        return True, None
    except Exception as e:
        logger.exception(f"execute_add_user failed: {e}")
        if "already have user" in str(e):
            context.user_data.pop("hotspot_add_session", None)
            return False, "duplicate"
        return False, str(e)'''

    content = content.replace(old_func, new_func)

    with open("bot/handlers/hotspot_common.py", "w", encoding="utf-8") as f:
        f.write(content)

refactor_hotspot_add()
refactor_hotspot_common()
print("Done")

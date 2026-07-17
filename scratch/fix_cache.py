import re

with open('core/hotspot_manager.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Add invalidate to add_user where it says logger.info("Created %d hotspot users successfully.", created_count)
code = re.sub(
    r'(logger\.info\("Created %d hotspot users successfully\.", created_count\)\n\s*)(return True, None)',
    r'\1self.invalidate_users_cache(router_key)\n            \2',
    code
)

# Add invalidate to edit_user
code = re.sub(
    r'(self\._api\.execute\(\n\s*router_key, "ip/hotspot/user/set", \*\*kwargs\n\s*\)\n\s*)(return True, None)',
    r'\1self.invalidate_users_cache(router_key)\n        \2',
    code
)

# reset_user_counters
code = re.sub(
    r'(self\._api\.execute\(router_key, "ip/hotspot/user/reset-counters", \*\*\{"numbers": user_id\}\)\n\s*)(return True, None)',
    r'\1self.invalidate_users_cache(router_key)\n        \2',
    code
)

# enable_user
code = re.sub(
    r'(self\._api\.execute\(router_key, "ip/hotspot/user/enable", \*\*\{"numbers": user_id\}\)\n\s*)(return True, None)',
    r'\1self.invalidate_users_cache(router_key)\n        \2',
    code
)

# disable_user
code = re.sub(
    r'(self\._api\.execute\(router_key, "ip/hotspot/user/disable", \*\*\{"numbers": user_id\}\)\n\s*)(return True, None)',
    r'\1self.invalidate_users_cache(router_key)\n        \2',
    code
)

with open('core/hotspot_manager.py', 'w', encoding='utf-8') as f:
    f.write(code)

import re

with open('core/hotspot_manager.py', 'r', encoding='utf-8') as f:
    code = f.read()

# patch edit_user
code = re.sub(
    r'(logger\.info\(f"Edited hotspot user \{user_id\} on \{router_key\}"\)\n\s*)(return result)',
    r'\1self.invalidate_users_cache(router_key)\n        \2',
    code
)

# patch reset_user_counters
code = re.sub(
    r'(logger\.info\(f"Reset counters for hotspot user \{user_id\} on \{router_key\}"\)\n\s*)(return result)',
    r'\1self.invalidate_users_cache(router_key)\n        \2',
    code
)

# patch enable_user
code = re.sub(
    r'(logger\.info\(f"Enabled hotspot user \{user_id\} on \{router_key\}"\)\n\s*)(return result)',
    r'\1self.invalidate_users_cache(router_key)\n        \2',
    code
)

# patch disable_user
code = re.sub(
    r'(logger\.info\(f"Disabled hotspot user \{user_id\} on \{router_key\}"\)\n\s*)(return result)',
    r'\1self.invalidate_users_cache(router_key)\n        \2',
    code
)

with open('core/hotspot_manager.py', 'w', encoding='utf-8') as f:
    f.write(code)

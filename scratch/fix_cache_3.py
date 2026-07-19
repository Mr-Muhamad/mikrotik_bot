import re

with open('core/hotspot_manager.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = re.sub(
    r'(logger\.info\(f"Added hotspot user \{name\} on \{router_key\}"\)\n\s*)(return result)',
    r'\1self.invalidate_users_cache(router_key)\n        \2',
    code
)

code = re.sub(
    r'(logger\.info\(f"Created \{len\(cards\)\} hotspot users on \{router_key\}"\)\n\s*)(return cards)',
    r'\1self.invalidate_users_cache(router_key)\n        \2',
    code
)

with open('core/hotspot_manager.py', 'w', encoding='utf-8') as f:
    f.write(code)

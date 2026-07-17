import re

with open('core/userman_manager.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Add import
if 'from core.cache import TTLCache' not in code:
    code = code.replace(
        'from core.mikrotik_api import mikrotik_api',
        'from core.mikrotik_api import mikrotik_api\nfrom core.cache import TTLCache'
    )

# Add cache instance to __init__
if 'self._users_cache' not in code:
    code = code.replace(
        'self._api_override = api',
        'self._api_override = api\n        self._users_cache = TTLCache(max_size=20, ttl=5)\n        self._sessions_cache = TTLCache(max_size=20, ttl=5)'
    )

# Add _get_all_users_cached
get_users_code = """
    def _get_all_users_cached(self, router_key: str, base_path: str) -> list[dict]:
        cached = self._users_cache.get(router_key)
        if cached is not None:
            return cached
        try:
            users = self._api.execute(router_key, f"{base_path}/user/print")
            self._users_cache.set(router_key, users)
            return users
        except Exception:
            return []

    def invalidate_users_cache(self, router_key: str):
        self._users_cache.invalidate(router_key)
        self._sessions_cache.invalidate(router_key)
"""
if '_get_all_users_cached' not in code:
    code = code.replace(
        'def _generate_digits(self, length: int) -> str:',
        get_users_code.lstrip() + '\n    def _generate_digits(self, length: int) -> str:'
    )

# Replace list_users body
code = re.sub(
    r'(def list_users\(self, router_key: str, limit: int = 50\) -> list\[dict\]:\n\s*base_path = mikrotik_api\.get_userman_base_path\(router_key\)\n\s*)(results = self\._api\.execute\(router_key, f"\{base_path\}/user/print"\)\n\s*return results\[:limit\])',
    r'\1all_users = self._get_all_users_cached(router_key, base_path)\n        return all_users[:limit]',
    code
)

# Replace search_users fallback
code = re.sub(
    r'(if not results:\n\s*)(results = self\._api\.execute\(router_key, f"\{base_path\}/user/print"\))',
    r'\1results = self._get_all_users_cached(router_key, base_path)',
    code
)

# Replace get_user fallback to search
code = re.sub(
    r'(results = self\._api\.execute\(router_key, f"\{base_path\}/user/print"\))',
    r'results = self._get_all_users_cached(router_key, base_path)',
    code
)

# Add invalidate_users_cache(router_key) to delete_user, enable_user, disable_user, reset_user_counters, add_profile_to_user, _create_user
code = re.sub(r'(def delete_user\(self, router_key: str, username: str\) -> list\[dict\]:[\s\S]*?logger\.info\(f"Deleted User Manager user \{username\} on \{router_key\}"\)\n\s*)(return result)', r'\1self.invalidate_users_cache(router_key)\n        \2', code)

code = re.sub(r'(def enable_user\(self, router_key: str, username: str\) -> list\[dict\]:[\s\S]*?logger\.info\(f"Enabled User Manager user \{username\} on \{router_key\}"\)\n\s*)(return result)', r'\1self.invalidate_users_cache(router_key)\n        \2', code)

code = re.sub(r'(def disable_user\(self, router_key: str, username: str\) -> list\[dict\]:[\s\S]*?logger\.info\(f"Disabled User Manager user \{username\} on \{router_key\}"\)\n\s*)(return result)', r'\1self.invalidate_users_cache(router_key)\n        \2', code)

code = re.sub(r'(def reset_user_counters\(self, router_key: str, username: str\) -> list\[dict\]:[\s\S]*?logger\.info\(f"Reset counters for User Manager user \{username\} on \{router_key\}"\)\n\s*)(return result)', r'\1self.invalidate_users_cache(router_key)\n        \2', code)

code = re.sub(r'(def _create_user\(self, router_key, username, password, profile, comment="", caller_id=""\):[\s\S]*?logger\.info\(f"Created User Manager user \{username\} successfully."\)\n\s*)(return True, None)', r'\1self.invalidate_users_cache(router_key)\n            \2', code)

with open('core/userman_manager.py', 'w', encoding='utf-8') as f:
    f.write(code)

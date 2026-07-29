_all_items = [
    "backup_service",
    "hotspot_manager",
    "mikrotik_api",
    "profile_sync",
    "stats_manager",
    "userman_manager",
]
__all__ = _all_items  # type: ignore[reportUnsupportedDunderAll]  # resolved via __getattr__


def __getattr__(name: str):
    if name == "backup_service":
        from core.backup_service import backup_service as _svc
        return _svc
    if name == "hotspot_manager":
        from core.hotspot_manager import hotspot_manager as _hm
        return _hm
    if name == "mikrotik_api":
        from core.mikrotik_api import mikrotik_api as _api
        return _api
    if name == "profile_sync":
        from core.profile_sync import profile_sync as _ps
        return _ps
    if name == "stats_manager":
        from core.stats import stats_manager as _sm
        return _sm
    if name == "userman_manager":
        from core.userman_manager import userman_manager as _um
        return _um
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return __all__

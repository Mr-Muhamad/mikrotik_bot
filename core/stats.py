import logging
from typing import Any

from core.mikrotik_api import mikrotik_api
from core.mikrotik_client import MikrotikClient

logger = logging.getLogger(__name__)


class StatsManager:
    """Retrieves and formats Hotspot and User Manager statistics from MikroTik routers."""

    def __init__(self, api: MikrotikClient | None = None):
        self._api_override = api

    @property
    def _api(self) -> MikrotikClient:
        """Injected client, or the shared module singleton (late-bound for tests)."""
        return self._api_override if self._api_override is not None else mikrotik_api

    def get_hotspot_stats(self, router_key: str) -> dict[str, Any] | None:
        """Return aggregated hotspot user counts and total byte usage."""
        try:
            all_users = self._api.execute(
                router_key,
                "ip/hotspot/user/print",
                **{".proplist": ".id,bytes-in,bytes-out"},
            )
            active_users = self._api.execute(
                router_key, "ip/hotspot/active/print", **{".proplist": ".id"}
            )

            total = len(all_users)
            active = len(active_users)
            inactive = total - active

            total_bytes = 0
            for user in all_users:
                bytes_in = int(user.get("bytes-in", 0) or 0)
                bytes_out = int(user.get("bytes-out", 0) or 0)
                total_bytes += bytes_in + bytes_out

            return {
                "total_users": total,
                "active_users": active,
                "inactive_users": inactive,
                "total_bytes": total_bytes,
            }
        except Exception as e:
            logger.error(f"Error getting hotspot stats: {e}")
            return None

    def get_userman_stats(self, router_key: str) -> dict[str, Any] | None:
        """Return User Manager card counts by enabled/disabled status."""
        try:
            base_path = self._api.get_userman_base_path(router_key)
            users = self._api.execute(
                router_key, f"{base_path}/user/print", **{".proplist": ".id,disabled"}
            )

            total = len(users)
            enabled = sum(1 for u in users if str(u.get("disabled", "false")).lower() != "true")
            disabled = total - enabled

            return {
                "total_users": total,
                "enabled_users": enabled,
                "disabled_users": disabled,
            }
        except Exception as e:
            logger.error(f"Error getting userman stats: {e}")
            return None

    def format_hotspot_stats(self, stats: dict[str, Any] | None, router_name: str) -> str:
        """Format hotspot stats dict into an Arabic display string."""
        from utils.formatters import format_hotspot_stats as _fmt

        return _fmt(stats, router_name)

    def format_userman_stats(self, stats: dict[str, Any] | None, router_name: str) -> str:
        """Format User Manager stats dict into an Arabic display string."""
        from utils.formatters import format_userman_stats as _fmt

        return _fmt(stats, router_name)

    def format_hotspot_usage_report(self, report: dict[str, Any], router_name: str) -> str:
        """Format a Hotspot usage report dict into an Arabic Telegram summary."""
        from utils.formatters import format_hotspot_usage_report as _fmt

        return _fmt(report, router_name)

    def get_week_trend(self, router_key: str) -> list[dict[str, Any]]:
        """قراءة snapshots آخر 7 أيام من DB لعرض الـ trend.

        يُعيد قائمة dicts بترتيب من الأقدم للأحدث:
        {"snapshot_date", "active_users", "total_users", "bytes_in", "bytes_out"}
        """
        from database.repositories.stats_snapshots import get_week_snapshots

        return get_week_snapshots(router_key)

    def format_trend_chart(self, snapshots: list[dict[str, Any]]) -> str:
        """تنسيق آخر 7 أيام كـ ASCII bar chart نصي بسيط.

        كل سطر: التاريخ | شريط | عدد المستخدمين
        """
        from utils.formatters import format_trend_chart as _fmt

        return _fmt(snapshots)

    def format_vs_yesterday(self, current: dict[str, Any], yesterday: dict[str, Any] | None) -> str:
        """مقارنة المستخدمين النشطين اليوم مقابل الأمس.

        يُعيد نص HTML مثل: ↑5 مقارنةً بالأمس (25 → 30)
        """
        from utils.formatters import format_vs_yesterday as _fmt

        return _fmt(current, yesterday)


stats_manager = StatsManager()

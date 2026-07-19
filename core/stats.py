import logging
from core.mikrotik_api import mikrotik_api
from core.mikrotik_client import MikrotikClient
from utils.formatters import format_bytes

logger = logging.getLogger(__name__)


class StatsManager:
    """Retrieves and formats Hotspot and User Manager statistics from MikroTik routers."""

    def __init__(self, api: MikrotikClient | None = None):
        self._api_override = api

    @property
    def _api(self) -> MikrotikClient:
        """Injected client, or the shared module singleton (late-bound for tests)."""
        return self._api_override if self._api_override is not None else mikrotik_api

    def get_hotspot_stats(self, router_key: str) -> dict | None:
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

    def get_userman_stats(self, router_key: str) -> dict | None:
        """Return User Manager card counts by enabled/disabled status."""
        try:
            base_path = self._api.get_userman_base_path(router_key)
            users = self._api.execute(
                router_key, f"{base_path}/user/print", **{".proplist": ".id,disabled"}
            )

            total = len(users)
            enabled = sum(
                1 for u in users if str(u.get("disabled", "false")).lower() != "true"
            )
            disabled = total - enabled

            return {
                "total_users": total,
                "enabled_users": enabled,
                "disabled_users": disabled,
            }
        except Exception as e:
            logger.error(f"Error getting userman stats: {e}")
            return None

    def format_hotspot_stats(self, stats: dict | None, router_name: str) -> str:
        """Format hotspot stats dict into an Arabic display string."""
        if not stats:
            return "❌ خطأ في جلب إحصائيات Hotspot"

        bytes_str = format_bytes(str(stats["total_bytes"]))

        return (
            f"📊 إحصائيات Hotspot - {router_name}\n\n"
            f"👥 إجمالي المستخدمين: {stats['total_users']}\n"
            f"🟢 نشط: {stats['active_users']}\n"
            f"🔴 غير نشط: {stats['inactive_users']}\n"
            f"📦 إجمالي البيانات: {bytes_str}"
        )

    def format_userman_stats(self, stats: dict | None, router_name: str) -> str:
        """Format User Manager stats dict into an Arabic display string."""
        if not stats:
            return "❌ خطأ في جلب إحصائيات User Manager"

        return (
            f"📊 إحصائيات User Manager - {router_name}\n\n"
            f"🎫 إجمالي الكروت: {stats['total_users']}\n"
            f"🟢 نشطة: {stats['enabled_users']}\n"
            f"🔴 منتهية/معطلة: {stats['disabled_users']}"
        )

    def format_hotspot_usage_report(self, report: dict, router_name: str) -> str:
        """Format a Hotspot usage report dict into an Arabic Telegram summary."""
        if not report or report.get("total", 0) == 0:
            return f"📊 تقرير استخدام Hotspot - {router_name}\n\n📭 لا يوجد مستخدمون لإنشاء تقرير."

        lines = [
            f"📊 تقرير استخدام Hotspot - {router_name}",
            "",
            f"👥 إجمالي المستخدمين: {report['total']}",
            f"🟢 نشط: {report['active']}",
            f"🔴 معطل: {report['disabled']}",
            f"📊 بحد بيانات: {report['with_limit']}",
            f"📦 إجمالي البيانات: {report['total_bytes_str']}",
            "",
            f"⏳ مقترب من الحد: {len(report['near_limit'])}",
            f"⌛ منتهٍ (وصل الحد): {len(report['expired'])}",
            f"💤 غير نشط: {len(report['inactive'])}",
            "",
            "🔝 الأكثر استهلاكاً:",
        ]
        for r in report.get("top_consumers", [])[:5]:
            lines.append(f"• {r['name']}: {r['total_str']} ({r['percent']:.0f}%)")
        return "\n".join(lines)

    def get_week_trend(self, router_key: str) -> list[dict]:
        """قراءة snapshots آخر 7 أيام من DB لعرض الـ trend.

        يُعيد قائمة dicts بترتيب من الأقدم للأحدث:
        {"snapshot_date", "active_users", "total_users", "bytes_in", "bytes_out"}
        """
        from database.repositories.stats_snapshots import get_week_snapshots

        return get_week_snapshots(router_key)

    def format_trend_chart(self, snapshots: list[dict]) -> str:
        """تنسيق آخر 7 أيام كـ ASCII bar chart نصي بسيط.

        كل سطر: التاريخ | شريط | عدد المستخدمين
        """
        if not snapshots:
            return ""
        max_active = max((s.get("active_users", 0) for s in snapshots), default=1) or 1
        lines = []
        for s in snapshots:
            day = s.get("snapshot_date", "")[-5:]  # MM-DD فقط
            active = s.get("active_users", 0)
            bar_len = round((active / max_active) * 8)
            bar = "█" * bar_len
            lines.append(f"{day} | {bar:<8} {active}")
        return "\n".join(lines)

    def format_vs_yesterday(self, current: dict, yesterday: dict | None) -> str:
        """مقارنة المستخدمين النشطين اليوم مقابل الأمس.

        يُعيد نص HTML مثل: ↑5 مقارنةً بالأمس (25 → 30)
        """
        if not yesterday:
            return ""
        prev = yesterday.get("active_users", 0)
        curr = current.get("active_users", 0)
        diff = curr - prev
        if diff > 0:
            arrow = "↑"
        elif diff < 0:
            arrow = "↓"
        else:
            arrow = "↔"
        return f"{arrow}{abs(diff)} مقارنةً بالأمس ({prev} → {curr})"


stats_manager = StatsManager()

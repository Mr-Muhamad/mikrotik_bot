import contextlib
import logging
import os
import re
import threading
import time
from typing import Any

from librouteros import connect
from librouteros.exceptions import LibRouterosError

from config import DEFAULT_API_PORT, FILE_SERVER_PORT, FILE_SERVER_SECRET, ROUTER_KEY_PREFIX
from core.connection_pool import API_TIMEOUT, LONG_TIMEOUT, ConnectionPool
from core.mikrotik_client import MikrotikClient, RouterOSResponse
from database.models import get_router_by_id, get_router_display_name

logger = logging.getLogger(__name__)

_MIN_INTERVAL = 0.1  # 100ms بين الأوامر لنفس الراوتر

# أخطاء نهائية: إعادة المحاولة لن تفيدين لأن السبب في أمر الراوتر نفسه وليس في الاتصال
NON_RETRYABLE_ERRORS = {"unknown parameter", "no such command"}


class MikrotikAPI:
    """Facade over ConnectionPool providing command execution and router metadata.

    Implements the :class:`core.mikrotik_client.MikrotikClient` Protocol.
    """

    def __init__(self):
        self._pool = ConnectionPool()
        self._rate_lock = threading.Lock()
        self._last_api_call: dict[str, float] = {}

    # ──────────────────────────────────────────────────────────────
    #  Metadata helpers (unchanged)
    # ──────────────────────────────────────────────────────────────

    def get_router_name(self, router_key: str = "router1") -> str:
        cached = self._pool.get_cached_name(router_key)
        if cached is not None:
            return cached
        if router_key.startswith(ROUTER_KEY_PREFIX):
            db_id = router_key.replace(ROUTER_KEY_PREFIX, "")
            router_cfg = get_router_by_id(int(db_id), decrypt=False)
            if router_cfg:
                name = get_router_display_name(router_cfg)
                self._pool.set_cached_name(router_key, name)
                return name
        return "لم يتم اختيار روتر"

    def invalidate_router_name(self, router_key: str):
        self._pool.invalidate_name(router_key)

    def invalidate_version(self, router_key: str):
        """يلغي كاش الإصدار المخزّن للراوتر.

        يُستخدم بعد ترقية RouterOS أو إعادة تسمية/إعادة ضبط الراوتر لضمان
        إعادة جلب الإصدار واختيار مسار User Manager الصحيح (v6 مقابل v7).
        """
        self._pool.invalidate_version(router_key)

    def get_cached_version(self, router_key: str = "router1") -> str | None:
        """Returns the version from cache without hitting the network."""
        return self._pool.get_version(router_key)

    def get_version(self, router_key: str = "router1") -> str:
        cached = self.get_cached_version(router_key)
        if cached:
            return cached
        try:
            # execute_long (120s) عوضاً عن execute (30s): جلب الإصدار حرج لاختيار
            # مسار User Manager (v6/v7)، والراوتر البطيء تحت الحمل قد يتجاوز 30s.
            result = self.execute_long(router_key, "system/resource/print")
            if result:
                version = result[0].get("version", "unknown")
                self._pool.set_version(router_key, version)
                return version
        except (LibRouterosError, ConnectionError, OSError) as e:
            # الفشل متحمَّل (نعود إلى v6)، لذا WARNING أدق من ERROR لئلا يملأ السجلات.
            logger.warning(f"Failed to get version for {router_key}: {e}")
        return "unknown"

    def is_version_7(self, router_key: str = "router1") -> bool:
        version = self.get_version(router_key)
        return version.startswith("7")

    def get_userman_base_path(self, router_key: str = "router1") -> str:
        version = self.get_version(router_key)
        if not version or version == "unknown":
            logger.warning(f"Unknown RouterOS version for {router_key}, defaulting to v6 API path")
            return "tool/user-manager"
        try:
            major = int(version.split(".")[0])
            return "user-manager" if major >= 7 else "tool/user-manager"
        except (ValueError, IndexError):
            return "tool/user-manager"

    def close(self) -> None:
        self._pool.close_all()

    def get_metrics(self) -> dict[str, Any]:
        return self._pool.get_metrics()

    def get_router_info(self, router_key: str) -> dict[str, Any]:
        return self._pool.get_router_info(router_key)

    def has_active_connection(self, router_key: str) -> bool:
        return self._pool.has_active_connection(router_key)

    @contextlib.contextmanager
    def _connection_ctx(self, router_key: str, timeout: int, force_reconnect: bool = False):
        if force_reconnect:
            api = self._pool.reconnect(router_key, timeout=timeout)
        else:
            api = self._pool.get_connection(router_key, timeout=timeout)

        broken = False
        try:
            yield api
        except (LibRouterosError, ConnectionError, OSError) as e:
            if any(pat in str(e) for pat in NON_RETRYABLE_ERRORS):
                broken = False
            else:
                broken = True
            raise
        except Exception:
            broken = True
            raise
        finally:
            self._pool.release_connection(router_key, api, broken=broken)

    def check_connection_health(self, router_key: str) -> tuple[bool, str]:
        """فحص صحة الاتصال بالروتر بشكل استباقي."""
        try:
            self._throttle(router_key)
            with self._connection_ctx(router_key, timeout=API_TIMEOUT) as api:
                result = self._call_command(api, "system/resource/print")
                if result:
                    return True, "healthy"
                return False, "empty_response"
        except (LibRouterosError, ConnectionError, OSError) as e:
            logger.warning(f"Health check failed for {router_key}: {e}")
            return False, str(e)

    # ──────────────────────────────────────────────────────────────
    #  Rate limiter
    # ──────────────────────────────────────────────────────────────

    def _throttle(self, router_key: str):
        with self._rate_lock:
            now = time.monotonic()
            last = self._last_api_call.get(router_key, 0.0)
            elapsed = now - last
            sleep_needed = max(0.0, _MIN_INTERVAL - elapsed)
            self._last_api_call[router_key] = now + sleep_needed
        if sleep_needed > 0:
            time.sleep(sleep_needed)

    # ──────────────────────────────────────────────────────────────
    #  Low-level building blocks
    # ──────────────────────────────────────────────────────────────

    def _call_command(self, api: Any, command: str, **kwargs: object) -> RouterOSResponse:
        """ينفذ أمر MikroTik واحد على اتصال موجود (بدون retry)."""
        parts = command.split("/")
        cmd = parts.pop()
        cmd_path = api.path(*parts)
        if kwargs:
            return list(cmd_path(cmd, **kwargs))
        return list(cmd_path(cmd))

    def _debug_log(self, method: str, command: str, kwargs: dict[str, Any]):
        """يسجل kwargs مع إخفاء كلمات المرور."""
        if kwargs:
            sanitized = {k: ("***" if "password" in k.lower() else v) for k, v in kwargs.items()}
            logger.debug(f"{method} {command} kwargs={sanitized}")

    # ──────────────────────────────────────────────────────────────
    #  Core execution template
    # ──────────────────────────────────────────────────────────────

    def _execute_with_retry(
        self, router_key: str, command: str, timeout: int, **kwargs: object
    ) -> RouterOSResponse:
        """القالب الأساسي: throttle → تنفيذ → retry عند الخطأ القابل للإصلاح."""
        self._throttle(router_key)
        try:
            with self._connection_ctx(router_key, timeout=timeout) as api:
                self._debug_log("_execute_with_retry", command, kwargs)
                return self._call_command(api, command, **kwargs)
        except (LibRouterosError, ConnectionError, OSError) as e:
            if command == "system/reboot":
                logger.info(f"Reboot command sent - connection may be lost: {e}")
                return []
            if any(pat in str(e) for pat in NON_RETRYABLE_ERRORS):
                logger.debug(f"Non-retryable error for {command} on {router_key}: {e}")
                raise

            logger.warning(
                f"Error executing {command} on {router_key}: {e}, retrying with fresh connection..."
            )
            try:
                with self._connection_ctx(
                    router_key, timeout=timeout, force_reconnect=True
                ) as new_api:
                    return self._call_command(new_api, command, **kwargs)
            except (LibRouterosError, ConnectionError, OSError) as e2:
                logger.error(f"Retry failed for {command} on {router_key}: {e2}")
                raise

    # ──────────────────────────────────────────────────────────────
    #  Public API — thin wrappers
    # ──────────────────────────────────────────────────────────────

    def execute(self, router_key: str, command: str, **kwargs: object) -> RouterOSResponse:
        """الأمر العادي — مهلة 30 ثانية، يعيد المحاولة عند الخطأ."""
        return self._execute_with_retry(router_key, command, API_TIMEOUT, **kwargs)

    def execute_long(self, router_key: str, command: str, **kwargs: object) -> RouterOSResponse:
        """أمر طويل — مهلة 120 ثانية، يعيد المحاولة عند الخطأ."""
        return self._execute_with_retry(router_key, command, LONG_TIMEOUT, **kwargs)

    def execute_non_blocking(self, router_key: str, command: str, **kwargs: object) -> None:
        """أمر غير متزامن — لا يعيد المحاولة، يسجل الخطأ ويتجاوزه."""
        try:
            with self._connection_ctx(router_key, timeout=API_TIMEOUT) as api:
                self._debug_log("execute_non_blocking", command, kwargs)
                self._call_command(api, command, **kwargs)
                logger.info(f"Non-blocking command sent: {command}")
        except (LibRouterosError, ConnectionError, OSError) as e:
            logger.info(f"Non-blocking command sent - connection may be lost: {e}")
        except Exception as e:
            logger.info(f"Non-blocking command sent with error (expected): {e}")

    # ──────────────────────────────────────────────────────────────
    #  Connection test (independent — uses raw librouteros connect)
    # ──────────────────────────────────────────────────────────────

    def test_connection(
        self, ip: str, username: str, password: str, port: int = DEFAULT_API_PORT
    ) -> tuple[bool, str, str]:
        api = None
        # Fast reachability check (2 seconds) before full Mikrotik authentication
        import socket

        try:
            with socket.create_connection((ip, port), timeout=2.0):
                pass
        except OSError as e:
            logger.warning(f"Fast port check failed for {ip}:{port} - {e}")
            return False, f"Port {port} closed/unreachable", ""

        try:
            api = connect(
                username=username,
                password=password,
                host=ip,
                port=port,
                encoding="utf-8",
                timeout=API_TIMEOUT,
            )
            result = list(api.path("system", "resource")("print"))
            version = str(result[0].get("version", "unknown")) if result else "unknown"
            identity_result = list(api.path("system", "identity")("print"))
            identity = str(identity_result[0].get("name", ip)) if identity_result else ip
            return True, version, identity
        except LibRouterosError as e:
            logger.error(f"test_connection LibRouterosError for {ip}:{port}: {e}")
            return False, self._classify_connect_failure(e, ip, port), ""
        except OSError as e:
            # مهلة الاتصال أو رفضه متوقّفان عند فحص راوترات تختبرية/غير موجودة
            # (مثل عناوين TEST-NET المحجوزة)؛ نسجّلها كـ WARNING لتقليل الضوضاء.
            if self._is_timeout_error(e):
                logger.warning(f"test_connection timeout for {ip}:{port}: {e}")
            else:
                logger.error(f"test_connection OSError for {ip}:{port}: {e}")
            ssl_hint = self._probe_api_ssl(ip, username, password)
            return False, self._classify_connect_failure(e, ip, port, ssl_hint), ""
        except Exception as e:
            logger.error(f"test_connection unexpected error for {ip}:{port}: {e}")
            return False, self._classify_connect_failure(e, ip, port), ""
        finally:
            if api:
                try:
                    api.close()
                except Exception as e:
                    logger.debug(f"Error closing test connection for {ip}: {e}")

    def _is_timeout_error(self, exc: Exception) -> bool:
        """يتحقق ما إذا كان الخطأ مهلة اتصال (winerror/errno 10060 أو نص timed out)."""
        msg = str(exc).lower()
        winerror = getattr(exc, "winerror", None)
        errno = getattr(exc, "errno", None)
        return (
            winerror in (10060,)
            or errno in (10060,)
            or "timed out" in msg
            or "10060" in msg
            or "timeout" in msg
        )

    def _sanitize_connect_detail(self, raw: str) -> str:
        """تنظيف نص خطأ الاتصال من أي أسرار محتملة قبل عرضه للمستخدم."""
        if not raw:
            return ""
        cleaned = re.sub(
            r"(?i)(password|passwd|secret|token)\s*[=:]\s*\S+",
            r"\1=***",
            raw,
        )
        return cleaned[:300]

    def _classify_connect_failure(
        self, exc: Exception, ip: str, port: int, ssl_hint: str = ""
    ) -> str:
        """يبني رسالة عربية واضحة وقابلة للفعل من خطأ اتصال raw."""
        msg = str(exc)
        lower = msg.lower()
        winerror = getattr(exc, "winerror", None)
        errno = getattr(exc, "errno", None)

        # مهلة الاتصال: الحزم تُسقط بصمت (جدار ناري / خدمة api معطّلة)
        if (
            winerror in (10060,)
            or errno in (10060,)
            or "timed out" in lower
            or "10060" in lower
            or "timeout" in lower
        ):
            text = (
                f"⏱️ انتهت مهلة الاتصال بـ {ip}:{port}. غالباً جدار ناري يمنع هذا المنفذ "
                f"أو أن خدمة api معطّلة على الراوتر. تحقق من:\n"
                f"• IP ▶ Services (تأكد أن api مفعّلة ومنفذها {port})\n"
                f"• IP ▶ Firewall ▶ Filter Rules (قاعدة accept لـ chain=input و tcp/{port})"
            )
            return text + ssl_hint

        # رفض الاتصال: المنفذ لا يستمع (خدمة api غير مفعّلة)
        if (
            winerror in (10061,)
            or errno in (10061,)
            or "refused" in lower
            or "10061" in lower
            or "connection refused" in lower
        ):
            text = (
                f"❌ رُفض الاتصال بـ {ip}:{port} (connection refused). خدمة api غير مفعّلة "
                f"على الراوتر أو لا تستمع على هذا المنفذ. فعّل خدمة api من IP ▶ Services."
            )
            return text + ssl_hint

        # خطأ توثيق من الراوتر
        if isinstance(exc, LibRouterosError) and any(
            kw in lower
            for kw in (
                "invalid user",
                "password",
                "login",
                "credential",
                "unauthorized",
                "wrong user",
            )
        ):
            return "🔑 فشل تسجيل الدخول إلى الروتر. اسم المستخدم أو كلمة المرور غير صحيح."

        # أي خطأ آخر: نعرض نصاً معقّماً
        sanitized = self._sanitize_connect_detail(msg)
        base = f"❌ تعذّر الاتصال بـ {ip}:{port}"
        return (base + (f": {sanitized}" if sanitized else ".")) + ssl_hint

    # ──────────────────────────────────────────────────────────────
    #  HTTP file transfer (replaces FTP)
    # ──────────────────────────────────────────────────────────────

    def _get_bot_host_for_router(self, router_key: str) -> str:
        """Return the bot host IP that the router can reach (from the bot's perspective)."""
        # In most setups the bot and router are on the same management network.
        # The user should set BOT_HOST in .env if the bot is behind NAT.
        from config import BOT_HOST

        return BOT_HOST

    def upload_file_to_router(self, router_key: str, local_path: str, remote_name: str) -> bool:
        """Serve a local file via HTTP and have the router fetch it.

        Uses: ``/tool/fetch url="http://BOT:PORT/files/NAME" dst-path="NAME"``
        """
        from core.backup.file_server import prepare_serve_file, cleanup_serve_file

        bot_host = self._get_bot_host_for_router(router_key)
        if not bot_host:
            logger.error("BOT_HOST not configured — cannot upload file to router")
            return False

        try:
            serve_name = prepare_serve_file(local_path, remote_name)
        except Exception as e:
            logger.error(f"Failed to stage file for upload: {e}")
            return False

        url = f"http://{bot_host}:{FILE_SERVER_PORT}/files/{serve_name}"
        try:
            self.execute_long(
                router_key,
                "tool/fetch",
                **{
                    "url": url,
                    "dst-path": remote_name,
                    "http-header-field": f"Authorization: Bearer {FILE_SERVER_SECRET}",
                },
            )
            logger.info(f"Router fetched {remote_name} from {url}")
            return True
        except Exception as e:
            logger.error(f"Router failed to fetch {remote_name}: {e}")
            return False
        finally:
            cleanup_serve_file(serve_name)

    def download_file_from_router(self, router_key: str, remote_name: str, local_dir: str) -> bool:
        """Tell the router to push a file to the bot via HTTP POST.

        Uses: ``/tool/fetch upload=yes url="http://BOT:PORT/upload"``
        """
        bot_host = self._get_bot_host_for_router(router_key)
        if not bot_host:
            logger.error("BOT_HOST not configured — cannot receive file from router")
            return False

        url = f"http://{bot_host}:{FILE_SERVER_PORT}/upload"
        try:
            self.execute_long(
                router_key,
                "tool/fetch",
                **{
                    "url": url,
                    "src-path": remote_name,
                    "upload": "yes",
                    "http-header-field": (
                        f"Authorization: Bearer {FILE_SERVER_SECRET}, "
                        f"X-Filename: {remote_name}, "
                        f"X-Router-Key: {router_key}"
                    ),
                },
            )
            logger.info(f"Router pushed {remote_name} to {url}")

            # The file arrives at BACKUP_DIR/uploads/<router_key>/<filename>
            upload_dir = os.path.join(
                os.path.dirname(os.path.dirname(local_dir)),
                "uploads",
                router_key,
            )
            src = os.path.join(upload_dir, remote_name)
            if os.path.isfile(src):
                os.makedirs(local_dir, exist_ok=True)
                dest = os.path.join(local_dir, remote_name)
                import shutil

                shutil.move(src, dest)
                return True
            logger.warning(f"File {remote_name} not found in upload dir after push")
            return False
        except Exception as e:
            logger.error(f"Router failed to push {remote_name}: {e}")
            return False

    def _probe_api_ssl(self, ip: str, username: str, password: str) -> str:
        """فحص استطلاعي لمنفذ 8729 (api-ssl) كسرّ تشخيصي فقط. لا يبدّل المسار الأساسي."""
        try:
            probe = connect(
                username=username,
                password=password,
                host=ip,
                port=8729,
                encoding="utf-8",
                timeout=3,
            )
            try:
                probe.close()
            except Exception:
                pass
            return (
                "\n\n💡 لاحظت أن منفذ 8729 (api-ssl) مفتوح على الراوتر. البوت يستخدم حالياً "
                "8728 (api النصّي) حسب إعدادات الأمان. إن رغبت باستخدام SSL راجع المسؤول."
            )
        except Exception:
            return ""


mikrotik_api: MikrotikClient = MikrotikAPI()

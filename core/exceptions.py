"""Custom exception hierarchy for MikroTik Bot.

يتيح هذا الملف التمييز بين أنواع الأخطاء وتسجيلها بـ context كافٍ
(router_key, user_id) بدلاً من الاعتماد على except Exception العام.

استخدام:
    from core.exceptions import RouterNotFoundError, RouterConnectionError, RouterCommandError
"""


class MikrotikBotError(Exception):
    """الصنف الأساسي لكل أخطاء البوت المخصصة."""


class RouterNotFoundError(MikrotikBotError):
    """الراوتر غير موجود في قاعدة البيانات أو المفتاح غير صالح."""


class RouterConnectionError(MikrotikBotError):
    """فشل الاتصال بالراوتر (شبكة، timeout، رفض اتصال)."""


class RouterCommandError(MikrotikBotError):
    """نجح الاتصال لكن الأمر فشل (unknown parameter، no such command، إلخ)."""

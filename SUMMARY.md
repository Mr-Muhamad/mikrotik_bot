## Objective
- إعادة هيكلة مجلدات النسخ الاحتياطي إلى `backups/RouterName/system/` و `backups/RouterName/userman/`
- إضافة FTP fallback للتحميل المحلي وإظهار أزرار تحميل بعد النسخ

## Important Details
- الدليل الجديد: `backups/<RouterName>/system/` ملفات مسطحة (لا مجلدات فرعية لكل نسخة)، و `backups/<RouterName>/userman/`
- آلية التحميل: HTTP push أولاً → FTP fallback → `download_backup_file()` في `core/backup/files.py`
- `resolve_userman_backup_file` قبلت `router_name` إضافياً للمسار الجديد
- أزرار التحميل (`get_backup_download_keyboard`) تُظهر الآن بعد كل نسخ ناجح عبر `_background_backup_job`
- `backup_restore.py` تستخدم الآن `path` من القائمة بدلاً من إعادة بناء المسار
- `cleanup_old_files` محلي في `system.py` باسم `_cleanup_old_files` لملفات `.backup` و `.rsc`

## Work State
### Completed
- `core/backup/files.py`: أضيفت `download_backup_file` + `resolve_userman_backup_file` قبلت `router_name`
- `core/backup/system.py`: هيكل `RouterName/system/` + `_cleanup_old_files` + `download_backup_file` + `created_files` في النتيجة
- `core/backup/userman.py`: هيكل `RouterName/userman/` + `download_backup_file` + `created_files` في النتيجة
- `core/backup/__init__.py`: أضيف `download_backup_file` للـ `__all__`
- `bot/messages.py`: أضيفت `BACKUP_DL_FTP_FALLBACK`, `BACKUP_DL_NO_BOT_HOST`, `BACKUP_DL_DOWNLOAD_HINT`
- `bot/handlers/backup.py`: أضيف `get_backup_download_keyboard` + تخزين `backup_downloaded_list` في `user_data` + استخدام `resolve_local_backup_file` لكلا النوعين
- `bot/handlers/backup_restore.py`: أزيل `resolve_userman_backup_file` — تستخدم `path` من `tar_files` مباشرة
- `core/backup_service.py`: `resolve_userman_backup_file` قبلت `router_name`
- `tests/core/test_backup_system.py`: إزالة patch لـ `cleanup_old_backups` ، patch لـ `download_backup_file`
- `tests/core/test_backup_userman.py`: تحديث مسارات `RouterName/userman`، patch لـ `download_backup_file`

### Next Move
- تشغيل مجموعة الاختبارات الكاملة للتأكد من عدم وجود تراجعات أخرى

## Relevant Files
- `core/backup/files.py`: `download_backup_file` + `resolve_userman_backup_file` (مُحدَّث)
- `core/backup/system.py`: مُعاد كتابته بالكامل
- `core/backup/userman.py`: مُعاد كتابته بالكامل
- `core/backup_service.py`: `resolve_userman_backup_file` أضيف `router_name`
- `bot/handlers/backup.py`: أضيف أزرار التحميل + تخزين `user_data`
- `bot/handlers/backup_restore.py`: أزيل `resolve_userman_backup_file`
- `bot/messages.py`: رسائل جديدة
- `tests/core/test_backup_system.py`: مُحدَّث
- `tests/core/test_backup_userman.py`: مُحدَّث

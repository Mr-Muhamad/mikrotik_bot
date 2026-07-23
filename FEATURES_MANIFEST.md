# MikroTik Telegram Bot - Features Manifest

## 1. Hotspot Management
- **Add User:** إضافة مستخدم فردي مدعوماً ببيانات آمنة (Dataclasses) ومدة الصلاحية، مع خيار لطباعة الكارت الخاص به.
- **Edit User:** تعديل المستخدمين المتاحين (كلمة السر، البروفايل، مدة الصلاحية، وحدود البيانات).
- **Search & Kick:** البحث عن المستخدمين عبر الذاكرة المُقسمة (In-Memory Pagination)، والقدرة على طرد الأجهزة النشطة المرتبطة بالحساب (Active Sessions).
- **Cards Generation:** توليد كروت عشوائية بنظام (Server-Side Pagination) للحد من استهلاك الذاكرة وإرسالها بتنسيق PDF.

## 2. User Manager (v6 & v7 Compatible)
- **User Management:** إنشاء مستخدمين ودفعات وباقات.
- **Search:** البحث وتقليب الصفحات للتحكم في حسابات نظام مدير المستخدمين.
- **Profile Fetching:** مزامنة بروفايلات User Manager وحفظها كاش للتقليل من استهلاك الـ API.

## 3. Router Discovery & Management
- **MNDP Scanner:** فحص وتخزين الروترات في الشبكة تلقائياً.
- **Manual Addition:** إضافة راوتر يدوي للاتصال (عبر IP، Port، Username، Password).
- **Session Protection:** الحماية عبر `conversation_timeout` للفصل بعد خمول المستخدم عن الراوتر المختار، بالإضافة لثوابت الاتصال التلقائية.
- **Watchdog:** مراقبة الاتصال الفعلي وإرسال تنبيهات (Up/Down) لمشرفي البوت.

## 4. Backup & Restore
- **System Backup:** أخذ نسخة كاملة من النظام وإرسالها للمشرف وحفظها محلياً.
- **User Manager Backup:** دعم للنسخ واستعادة قاعدة بيانات UM (تتوافق مع اختلاف المسارات في v6 و v7).
- **JobQueue Scheduler:** جدولة يومية آلية لسحب الـ Backups.

## 5. Security & Persistence
- **Alembic Migrations:** نظام مستدام لإدارة مخططات SQLite وتحديثها مستقبلاً بشكل ناعم.
- **Centralized Messages:** ملف موحد لرسائل النظام لدعم التوطين ومنع الـ Magic Strings.
- **Encrypted Storage:** تشفير `Fernet` آمن لكلمات مرور الروترات في قاعدة البيانات.
- **Error Handling:** كبح الأخطاء الحميدة (`Benign Errors`) ومنعها من إزعاج المستخدم وإصدار Logs غير هامة.
- **Admin Decorator:** حماية الوصول لجميع مسارات البوت والتأكد من تحديد راوتر نشط للعمليات الجارية.

## 6. Enterprise Security & Access Control Roles
- **Super Admin (`ADMIN_IDS`):** صلاحيات كاملة تشمل إدارة الروترات، الحذف الشامل، إعادة التشغيل (`/reboot`)، استعادة النسخ الاحتياطية، وتعيين أدوار المستخدمين.
- **Operator Role (`operator`):** صلاحيات تشغيلية محددة تشمل البحث، شحن وتعديل الحسابات، عرض الإحصائيات والتصدير دون امتلاك صلاحيات الحذف التدميري أو تعديل النظام.
- **Auditing & Traceability:** تسجيل كافة الإجراءات الحساسة في `audit_logs` برقم المشرف والوقت المعياري مع إمكانية التصدير بصيغة CSV.

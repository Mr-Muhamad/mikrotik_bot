# توافق أوامر وحقول RouterOS v6 مقابل v7

تاريخ التوثيق: 2026-07-09
الأساس: فحص كود المشروع الفعلي (`core/mikrotik_api.py`, `core/userman_manager.py`, `core/hotspot_manager.py`, `core/backup/userman.py`) + خطة الأولويات (الأولوية 4).

## 1. الكشف عن الإصدار

- `mikrotik_api.get_version(router_key)` يجلب الإصدار عبر `system/resource/print` ويخزّنه في كاش (`connection_pool.router_versions`) بصلاحية **24 ساعة**.
- `mikrotik_api.is_version_7(router_key)` يرجع `True` إذا بدأ الإصدار بـ `7`.
- عند جهل الإصدار (كاش فارغ أو خطأ)، تُعتمد القاعدة **المحافظة**: يُفترض v6 (`tool/user-manager`) لأنه الأقل عرضة لكسر المسار.
- بعد ترقية الراوتر أو إعادة تسميته، يُستدعى `mikrotik_api.invalidate_version(router_key)` لإبطال الكاش وإعادة الجلب (انظر الأولوية 6). كما تُبطل النسخة تلقائياً عند `reconnect()` وإغلاق الاتصال.

## 2. مصفوفة المسارات (paths)

| العملية | مسار v6 | مسار v7 | كيفية الحل في الكود |
|---|---|---|---|
| User Manager — المستخدمون | `tool/user-manager/user` | `user-manager/user` | `get_userman_base_path()` |
| User Manager — البروفايلات | `tool/user-manager/profile` | `user-manager/profile` | `get_userman_base_path()` |
| Hotspot users | `ip/hotspot/user` | `ip/hotspot/user` | متطابق |
| Hotspot hosts | `ip/hotspot/host` | `ip/hotspot/host` | متطابق |
| Hotspot active | `ip/hotspot/active` | `ip/hotspot/active` | متطابق |
| Hotspot profiles | `ip/hotspot/user/profile` | `ip/hotspot/user/profile` | متطابق |
| DHCP leases | `ip/dhcp-server/lease` | `ip/dhcp-server/lease` | متطابق |
| System backup | `system/backup/save` | `system/backup/save` | متطابق |
| System resource | `system/resource` | `system/resource` | متطابق |
| System identity | `system/identity` | `system/identity` | متطابق |

> كل المسارات أعلاه عدا User Manager متطابقة بين v6 وv7؛ لذلك لا يلزم تفرقة خاصة لها.

## 3. تفرقة User Manager (النقطة الحرجة)

`get_userman_base_path(router_key)` هو **المرجع المركزي الوحيد** لاختيار المسار:

```python
def get_userman_base_path(self, router_key="router1") -> str:
    version = self.get_version(router_key)
    if not version or version == "unknown":
        return "tool/user-manager"          # افتراض آمن = v6
    major = int(version.split(".")[0])
    return "user-manager" if major >= 7 else "tool/user-manager"
```

- v7 ≥ 7 → `user-manager`
- v6 أو جهل الإصدار → `tool/user-manager`

## 4. فوارق الحقول عند الاستعادة (User Manager)

User Manager في v7 أُعيدت كتابته من الصفر، لذا قد يرفض الراوتر حقلاً موجوداً في نسخة v6 (مثل `uptime`, `address-list`, `idle-timeout`, `keepalive-timeout`, `status-autorefresh`, `session-timeout` في البروفايلات). لذلك `userman_restore()` في `core/backup/userman.py` يعتمد استعادة **دفاعية**:

1. يحاول الإضافة بكامل الحقول الاختيارية.
2. إن فشل بخطأ يوحي برفض حقل (`unknown parameter`, `unknown property`, `no such item`, `expected end`, `unknown command`)، يعيد المحاولة **بأقل الحقول المطلوبة فقط**:
   - البروفايل: `name` + `shared-users`.
   - المستخدم: `name` + `profile` (دون `password`).
3. إن نجحت المحاولة المخفّضة، تُحسب كعنصر مستعاد (partial restore) ولا تُسجَّل كخطأ.
4. إن فشلت المحاولتان، تُسجَّل في `errors` ويُضبط `success=False`.

> **تنبيه حرج (2026-07-13):** ربط البروفايل بالمستخدم في RouterOS v7 يتم عبر **جدول منفصل**
> وليس كحقل على المستخدم. الأمر الصحيح لـ v7 هو:
> `user-manager/user-profile/add user=<اسم_المستخدم> profile=<اسم_البروفايل>`.
> أما في **RouterOS v6** فالبروفايل يُربَط عبر أمر مخصص:
> `tool/user-manager/user/create-and-activate-profile profile=<الاسم> numbers=<اسم_المستخدم> customer=admin`.
> لذلك `core/userman_manager.py::_create_user` لا يرسل `profile` على `add` في أي إصدار،
> بل يستدعي الأمر الصحيح حسب الإصدار بعد نجاح الإنشاء، ثم **يتحقق بالقراءة العكسية**
> (`user-profile/print`) ويعيد حالة الربط بدل إسقاط المستخدم أو ابتلاع الخطأ صامتاً
> (وهو سبب العَرَض القديم: «توليد الكروت ينجح لكن البروفايل لا يُربَط»).
> تحديد الإصدار يُستنتج من مسار القاعدة: `tool/user-manager` ⇒ v6، وإلا ⇒ v7.

العناصر الموجودة مسبقاً (بنفس الاسم) تُتخطّى ولا تُستبدل (`skipped`).

## 5. ملاحظات للتنفيذ المستقبلي

- أي أمر جديد يمس User Manager يجب أن يمر عبر `get_userman_base_path()` ولا يُعتمد مساره صراحةً.
- لا تُفرض API-SSL أو REST كمسار أساسي؛ بعض الراوترات (خاصة v6) لا تملك شهادة SSL، وREST لا يغطي v6 جيداً. المسار الموحّد هو `librouteros` على المنفذ `8728`.
- بعد ترقية RouterOS، ألغِ كاش الإصدار صراحةً (`invalidate_version`) قبل أي عملية تعتمد على المسار.

## 6. حارس ثابت لمنع انحدار v6/v7

`scripts/validate_routeros_paths.py` يفحص كل ملفات `core/` (عدا `mikrotik_api.py`
الذي يملك مُنتقي المسار) ويرفض أي استدعاء `execute`/`execute_long`/`execute_non_blocking`
يحوي مسار User Manager مكتوباً صراحةً (`user-manager` أو `tool/user-manager`)، سواء
كنصّ عادي أو داخل f-string. الهدف: منع تجاوز كشف الإصدار الذي يكسر أحد الإصدارين.

- يعمل ثابتاً (بلا راوتر) وصالح للـ CI.
- مغطّى باختبارات `tests/test_validate_routeros_paths.py`.
- التشغيل: `py -3.12 scripts/validate_routeros_paths.py` (يخرج بكود 1 عند وجود مخالفة).

## 7. نطاق مهارات RouterOS المرفقة (تنبيه v7)

مهارات `.kilo/skills/routeros-*` تغطّي **RouterOS v7 فقط** (تصرّح `routeros-fundamentals`
صراحةً أن v6 غير مغطّاة). لذلك تُستخدم كمرجع للتحقق من سلوك v7 فقط، بينما يحافظ
البوت على توافق v6 عبر `get_userman_base_path()` وكاش الإصدار. لا تُطبَّق افتراضات
هذه المهارات (مثل REST على المنفذ 80 كواجهة أساسية) على مسار الاتصال؛ يبقى
`librouteros/8728` هو الموحّد.

### نتيجة تدقيق التكامل مقابل v7 (2026-07-10)

بمراجعة `core/hotspot_manager.py` و`core/userman_manager.py` و`core/network_probe.py`
مقابل مهارات `routeros-hotspot`/`routeros-fundamentals`/`routeros-mndp`:

| العنصر | المسار/الحقول | الحالة لـ v6 وv7 |
|---|---|---|
| Hotspot users | `ip/hotspot/user` + `add`/`set`/`remove`/`print` | متطابق ✓ |
| حقول المستخدم | `name`, `password`, `profile`, `limit-bytes-total`, `limit-uptime`, `comment`, `disabled` | صالحة في الإصدارين ✓ |
| تصفير العدّاد | `ip/hotspot/user/reset-counters` بـ `numbers=` | صحيح ✓ |
| Hotspot hosts/active | `ip/hotspot/host`, `ip/hotspot/active` | متطابق ✓ |
| DHCP leases | `ip/dhcp-server/lease/print` | متطابق ✓ |
| MNDP | UDP 5678، TLV، uptime little-endian (type 10) | مطابق للمواصفة ✓ |
| User Manager | عبر `get_userman_base_path()` حصراً | v6/v7 مضبوط ✓ |

الخلاصة: التكامل صحيح للإصدارين ولم يلزم أي تعديل سلوكي؛ أُضيف الحارس (القسم 6)
لتثبيت هذا الضمان مستقبلاً.

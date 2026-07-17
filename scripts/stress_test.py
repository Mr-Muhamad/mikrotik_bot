import sys
import os
import asyncio
import psutil
import time
import logging

# إضافة مسار المشروع الرئيسي
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.models import get_saved_routers
from core.hotspot_manager import HotspotManager
from utils.async_blocking import run_blocking

# تقليل إزعاج السجلات
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("librouteros").setLevel(logging.WARNING)
logging.getLogger("core.mikrotik_api").setLevel(logging.ERROR)
logging.basicConfig(level=logging.WARNING)

hotspot_manager = HotspotManager()

async def test_worker(router_key: str, num_requests: int):
    """عامل ينفذ عدد محدد من الطلبات بشكل متتالٍ."""
    success = 0
    failed = 0
    for _ in range(num_requests):
        try:
            # نستخدم عملية قراءة بسيطة من Hotspot
            await run_blocking(hotspot_manager.search_users, router_key, "")
            success += 1
        except Exception:
            failed += 1
    return success, failed

async def main():
    print("=== بدء اختبار الضغط (Stress Test) ===")
    
    # محاولة الحصول على راوتر نشط من قاعدة البيانات
    routers = get_saved_routers(active_only=True)
    if not routers:
        print("❌ لم يتم العثور على أي راوتر نشط في قاعدة البيانات. يرجى إضافة راوتر عبر البوت أولاً.")
        return
    
    router = routers[0]
    router_key = f"discovered_{router['id']}"
    router_name = router.get('name_alias') or router.get('identity') or 'Unknown'
    print(f"📡 سيتم إجراء الاختبار على الراوتر: {router_name} ({router_key})")
    
    process = psutil.Process(os.getpid())
    mem_before = process.memory_info().rss / (1024 * 1024)
    print(f"📊 الذاكرة قبل الاختبار: {mem_before:.2f} MB")
    
    # إعدادات الاختبار
    TASKS_COUNT = 30         # عدد المهام المتزامنة (Concurrency)
    REQUESTS_PER_TASK = 5    # عدد الطلبات لكل مهمة
    TOTAL_REQUESTS = TASKS_COUNT * REQUESTS_PER_TASK
    
    print(f"🚀 سيتم إرسال {TOTAL_REQUESTS} طلب بشكل متزامن ({TASKS_COUNT} threads)...")
    
    # تصفير عداد الـ CPU
    psutil.cpu_percent(interval=None)
    
    start_time = time.time()
    
    # إنشاء وتشغيل المهام المتزامنة
    tasks = []
    for _ in range(TASKS_COUNT):
        tasks.append(asyncio.create_task(test_worker(router_key, REQUESTS_PER_TASK)))
        
    results = await asyncio.gather(*tasks)
    
    end_time = time.time()
    
    # قراءة الموارد بعد الاختبار
    cpu_usage = psutil.cpu_percent(interval=None)
    mem_after = process.memory_info().rss / (1024 * 1024)
    
    total_success = sum(r[0] for r in results)
    total_failed = sum(r[1] for r in results)
    elapsed = end_time - start_time
    
    print("\n=== نتائج الاختبار ===")
    print(f"✅ الطلبات الناجحة: {total_success}")
    print(f"❌ الطلبات الفاشلة: {total_failed}")
    print(f"⏱️ الوقت الإجمالي: {elapsed:.2f} ثانية")
    if elapsed > 0:
        print(f"⚡ معدل الطلبات: {TOTAL_REQUESTS / elapsed:.2f} طلب/ثانية")
    
    print("\n=== استهلاك الموارد ===")
    print(f"🧠 استهلاك المعالج (CPU): {cpu_usage}%")
    print(f"📈 الذاكرة بعد الاختبار: {mem_after:.2f} MB")
    print(f"🔄 فرق الذاكرة: {mem_after - mem_before:.2f} MB")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nتم إيقاف الاختبار يدوياً.")

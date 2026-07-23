"""Real Network Discovery Test Script.

Tests MNDP broadcast, ARP table scanning, and direct port 8728 check.
Run with: py -3.12 scripts/test_discovery.py
"""

import asyncio
import logging
import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.network_probe import ARPTableProbe, MNDPListenerProbe, PortScanProbe, merge_probe_results

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

async def run_real_discovery_test():
    print("=" * 60)
    print("🔍 بدء الاختبار الحقيقي لوظائف الاستكشاف (Neighbors & Probe Test)")
    print("=" * 60)

    # 1. Test MNDP (Neighbors)
    print("\n📡 [1/3] اختبار MNDP Broadcast (المسؤول عن جلب Neighbors)...")
    mndp_probe = MNDPListenerProbe(timeout=5.0)
    try:
        mndp_results = await mndp_probe.discover()
        print(f"✅ نتيجة MNDP: تم اكتشاف {len(mndp_results)} راوتر عبر البث الشبكي.")
        for item in mndp_results:
            print(f"   • IP: {item.get('ip')} | Identity: {item.get('identity')} | Board: {item.get('board')} | Version: {item.get('version')}")
    except PermissionError:
        print("⚠️ فشل MNDP: يتطلب تشغيل السكربت كـ Administrator لفتح منفذ UDP Raw Socket.")
    except Exception as e:
        print(f"❌ خطأ أثناء MNDP: {e}")

    # 2. Test ARP Table
    print("\n📋 [2/3] فحص جدول ARP المحلي للأجهزة المتصلة...")
    arp_probe = ARPTableProbe()
    arp_results = arp_probe.discover()
    print(f"✅ نتيجة ARP: تم العثور على {len(arp_results)} جهاز في جدول الشبكة المحلي.")
    for item in arp_results[:5]:
        print(f"   • IP: {item.get('ip')} | MAC: {item.get('mac')}")

    # 3. Direct Port Check (8728) on all ARP candidate IPs
    candidate_ips = [r["ip"] for r in arp_results if r.get("ip")]
    if "192.0.0.1" not in candidate_ips:
        candidate_ips.append("192.0.0.1")
    print(f"\n🔌 [3/3] فحص منفذ API (8728) لـ {len(candidate_ips)} جهاز مرشح...")
    port_probe = PortScanProbe(ips=candidate_ips, port=8728, timeout=1.5)
    port_results = await port_probe.discover()
    print(f"✅ نتيجة فحص API Port 8728: تم تأكيد {len(port_results)} راوتر MikroTik يستجيب على منفذ 8728.")
    for item in port_results:
        print(f"   • IP: {item.get('ip')} | Port 8728: 🟢 OPEN")


    # Summary
    all_routers = merge_probe_results(arp_results, port_results, mndp_results)
    print("\n" + "=" * 60)
    print(f"📊 الخلاصة الإجمالية: تم دمج واكتشاف {len(all_routers)} جهاز/راوتر.")
    for r in all_routers:
        print(f"   • {r.display_line()}")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_real_discovery_test())

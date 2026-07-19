import asyncio
import logging
from core.backup_service import backup_service
from core.connection_pool import connection_pool

logging.basicConfig(level=logging.INFO)

async def test():
    router_key = "discovered_317"
    
    # Check if router exists
    from database.models import get_saved_routers
    routers = get_saved_routers()
    found = any(f"discovered_{r['id']}" == router_key for r in routers)
    if not found:
        print(f"Router {router_key} not found in DB.")
        return
        
    print(f"Testing userman_backup for {router_key}...")
    um_res = backup_service.userman_backup(router_key)
    print("User Manager Backup Result:", um_res)
    
    print(f"Testing full_backup for {router_key}...")
    sys_res = backup_service.full_backup(router_key)
    print("System Backup Result:", sys_res)

if __name__ == "__main__":
    asyncio.run(test())

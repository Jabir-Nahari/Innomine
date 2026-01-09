
import sys
import asyncio
import traceback
import os
import time

# Add cwd to path
sys.path.append(os.getcwd())

async def test():
    print("=== DASHBOARD API VERIFICATION SCRIPT ===")
    
    print("\n[Step 1] Checking Imports...")
    try:
        from web_dashboard.main import get_dashboard_data, get_real_sensor_data, simulate_miner
        from db_interfaces.db import get_connection
        print("PASS: Imports successful.")
    except Exception as e:
        print(f"FAIL: Import error: {e}")
        return

    print("\n[Step 2] Testing Database Connection (Create/Close)...")
    try:
        start = time.time()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                res = cur.fetchone()
                print(f"PASS: DB Query 'SELECT 1' returned {res}. Time: {time.time()-start:.4f}s")
    except Exception as e:
        print(f"FAIL: DB Connection failed: {e}")
        return

    print("\n[Step 3] Testing get_real_sensor_data() (Fetching from 3 tables)...")
    try:
        start = time.time()
        data = get_real_sensor_data()
        print(f"PASS: Data fetched in {time.time()-start:.4f}s")
        print(f"      Result: {data}")
    except Exception as e:
        print(f"FAIL: get_real_sensor_data crashed: {e}")
        traceback.print_exc()

    print("\n[Step 4] Testing Full API Logic (simulate_miner + aggregation)...")
    try:
        res = await get_dashboard_data()
        health = res.get("health")
        miners = res.get("miners", [])
        print("PASS: API Logic Success.")
        print(f"      Active Workers: {len(miners)}")
        print(f"      Site Health: {health}")
        if len(miners) > 0:
            print(f"      Miner 1 (Real): {miners[0]}")
    except Exception as e:
        print(f"FAIL: API Logic crashed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test())

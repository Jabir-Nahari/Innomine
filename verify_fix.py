
import sys
import os

# Add cwd to path
sys.path.append(os.getcwd())

try:
    from web_dashboard.main import simulate_miner, get_battery_cap
    print("Import successful")
except Exception as e:
    print(f"Import Failed: {e}")
    sys.exit(1)

try:
    print("Testing get_battery_cap...")
    cap = get_battery_cap()
    print(f"Battery Cap: {cap}")
except Exception as e:
    print(f"get_battery_cap Failed: {e}")

try:
    print("Testing simulate_miner...")
    # Test Miner 1 (Real)
    data = {"co2_ppm": 500, "temperature_c": 22, "humidity_rh": 50}
    m1 = simulate_miner(1, data)
    print(f"Miner 1 OK: {m1.name} Real={m1.is_real_data}")
    
    # Test Miner 2 (Sim)
    m2 = simulate_miner(2, None)
    print(f"Miner 2 OK: {m2.name} Real={m2.is_real_data}")
    
except Exception as e:
    print(f"simulate_miner Failed: {e}")
    import traceback
    traceback.print_exc()


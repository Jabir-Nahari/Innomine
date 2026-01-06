from w1thermsensor import W1ThermSensor
import time

try:
    sensor = W1ThermSensor()
    print("Sensor found! Reading temperature...")
    
    while True:
        temperature = sensor.get_temperature()
        print(f"Temperature: {temperature:.2f}°C | {temperature * 9/5 + 32:.2f}°F")
        time.sleep(2)
        
except Exception as e:
    print(f"Error: {e}")
    print("Check your wiring and ensure 'dtoverlay=w1-gpio' is in config.txt")
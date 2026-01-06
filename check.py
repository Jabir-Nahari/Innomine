from gpiozero import Buzzer
from time import sleep

# If your buzzer makes noise when it shouldn't, 
# change active_high to False
buzzer = Buzzer(17, active_high=True) 

print("Buzzer test starting...")

try:
    while True:
        print("Beep")
        buzzer.on()
        sleep(0.5)
        
        print("Silence")
        buzzer.off()
        sleep(0.5)
except KeyboardInterrupt:
    print("Stopped by user")
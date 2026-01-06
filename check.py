from gpiozero import Buzzer

# Buzzer on BCM 15
bz = Buzzer(15)
bz.beep(on_time=0.1, off_time=0.1, n=3) # Beep 3 times quickly
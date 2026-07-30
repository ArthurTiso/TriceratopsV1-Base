import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setup(18, GPIO.IN)

while True:
    print(GPIO.input(18))
    time.sleep(0.2)

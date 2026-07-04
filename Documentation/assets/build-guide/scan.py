import board
import busio
from adafruit_pn532.i2c import PN532_I2C

i2c = busio.I2C(board.SCL, board.SDA)
pn532 = PN532_I2C(i2c)

pn532.SAM_configuration()

print("Waiting for NFC tag...")

while True:
    uid = pn532.read_passive_target(timeout=0.5)

    if uid:
        print("UID:", uid.hex())
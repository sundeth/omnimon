import board
import busio
from adafruit_pn532.i2c import PN532_I2C

i2c = busio.I2C(board.SCL, board.SDA)
pn532 = PN532_I2C(i2c, debug=True)

pn532.SAM_configuration()

while True:
    uid = pn532.read_passive_target(timeout=0.5)

    if uid:
        print("FOUND:", uid.hex())
import board
import busio
from adafruit_pn532.i2c import PN532_I2C

print("Opening I2C...")

i2c = busio.I2C(board.SCL, board.SDA)

print("Connecting to PN532...")

pn532 = PN532_I2C(i2c)

ic, ver, rev, support = pn532.firmware_version

print(f"IC: {ic}")
print(f"Firmware: {ver}.{rev}")

pn532.SAM_configuration()

print("Reader ready.")
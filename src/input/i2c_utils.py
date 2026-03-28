import time
import struct
import os

try:
    import smbus  # type: ignore
    HAS_SMBUS = True
except ImportError:
    HAS_SMBUS = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

import platform

IS_LINUX = platform.system() == "Linux"
IS_RPI = IS_LINUX and HAS_SMBUS  # Only True if running on Linux with smbus available

CW2015_ADDRESS = 0x62
CW2015_REG_VCELL = 0x02
CW2015_REG_SOC = 0x04
CW2015_REG_MODE = 0x0A
BMI160_ADDRESS = 0x69

class I2CUtils:
    def __init__(self):
        i2c_device_exists = os.path.exists("/dev/i2c-1")
        self.bus = smbus.SMBus(1) if IS_RPI and i2c_device_exists else None
        self.battery_addr = CW2015_ADDRESS
        self.bmi160_addr = BMI160_ADDRESS
        self.valid = IS_RPI and i2c_device_exists
        self.charging = False
        self.battery_percent = 0.0

        self._last_voltage = None
        self._charging_counter = 0  # For debounce

        if IS_RPI:
            self.quick_start()  # Initialize CW2015 at startup
            self.init_bmi160()

    def quick_start(self):
        """ Initialize CW2015 fuel gauge """
        if not IS_RPI:
            return
        try:
            self.bus.write_word_data(CW2015_ADDRESS, CW2015_REG_MODE, 0x30)
            time.sleep(1)  # Allow chip to calibrate
        except Exception as e:
            print(f"QuickStart error: {e}")

    def read_voltage(self):
        """ Read battery voltage and update charging status """
        if not IS_RPI:
            return None
        try:
            vcell = self.bus.read_word_data(CW2015_ADDRESS, CW2015_REG_VCELL)
            voltage = ((vcell & 0xFF) << 8 | (vcell >> 8)) * 0.305 / 1000

            # Charging detection logic
            if self._last_voltage is not None:
                if voltage > self._last_voltage + 0.002:  # Small threshold to avoid noise
                    self._charging_counter += 1
                else:
                    self._charging_counter = max(0, self._charging_counter - 1)
                # Require several consecutive increases to confirm charging
                self.charging = self._charging_counter >= 3
            self._last_voltage = voltage

            return voltage
        except Exception as e:
            print(f"Voltage read error: {e}")
            return None

    def read_capacity(self):
        """ Read battery capacity on RPI """
        if not IS_RPI:
            return None
        try:
            soc = self.bus.read_word_data(CW2015_ADDRESS, CW2015_REG_SOC)
            capacity = ((soc & 0xFF) << 8 | (soc >> 8)) / 256
            return capacity
        except Exception as e:
            print(f"Capacity read error: {e}")
            return None

    def get_battery_info(self):
        if HAS_PSUTIL:
            battery_stats = psutil.sensors_battery()
            if battery_stats == None:
                self.battery_percent = 0.0
                self.charging = True
            elif battery_stats.power_plugged == True:
                self.battery_percent = battery_stats.percent
                self.charging = True
            else:
                self.battery_percent = battery_stats.percent
                self.charging = False
        elif IS_RPI:
            self.battery_percent = self.read_capacity()
            self.charging = False
        else:
            self.battery_percent = 0.0
            self.charging = False
        return self.battery_percent, self.charging

    def test_battery(self):
        """ Run continuous battery monitoring """
        if IS_RPI:
            self.quick_start()  # Initialize fuel gauge

        while True:
            voltage = self.read_voltage()
            capacity = self.read_capacity()

            print("++++++++++++++++++++")
            print(f"?? Voltage: {voltage:.2f}V" if voltage else "Voltage Read Error")
            print(f"?? Battery: {capacity:.1f}%" if capacity else "Capacity Read Error")
            print("++++++++++++++++++++")

            time.sleep(2)

    def init_bmi160(self):
        if not IS_RPI:
            return
        try:
            self.bus.write_byte_data(self.bmi160_addr, 0x7E, 0xB6)  # Reset sensor
            time.sleep(0.1)
            self.bus.write_byte_data(self.bmi160_addr, 0x40, 0x28)  # Set range
            self.bus.write_byte_data(self.bmi160_addr, 0x41, 0x03)  # Set bandwidth
            self.bus.write_byte_data(self.bmi160_addr, 0x7E, 0x11)  # Enable accelerometer
            time.sleep(0.1)
        except Exception:
            self.valid = False

    def read_accel(self):
        if not self.valid or not IS_RPI:
            return 0.0, 0.0, 1.0  # Default Z-axis down
        try:
            data = self.bus.read_i2c_block_data(self.bmi160_addr, 0x12, 6)
            x = struct.unpack('<h', bytes(data[0:2]))[0]
            y = struct.unpack('<h', bytes(data[2:4]))[0]
            z = struct.unpack('<h', bytes(data[4:6]))[0]
            factor = 16384.0
            return x / factor, y / factor, z / factor
        except Exception:
            return None, None, None
import time
import os
import platform
import shutil

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# Cache system stats and update every 3 seconds to reduce overhead
last_update_time = 0
cached_temp, cached_cpu, cached_memory = None, None, None

def get_cpu_temp_linux():
    """Get CPU temperature on Linux, with fallback for Batocera."""
    # Check if vcgencmd exists
    if shutil.which("vcgencmd"):
        try:
            temp_str = os.popen("vcgencmd measure_temp").readline()
            return float(temp_str.replace("temp=", "").replace("'C\n", ""))
        except Exception:
            pass
    
    # Fallback: read from /sys/class/thermal
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return int(f.read()) / 1000.0
    except Exception:
        return None

def get_system_stats():
    """Fetch system stats only if at least 3 seconds have passed. Never crash if a value can't be obtained."""
    global last_update_time, cached_temp, cached_cpu, cached_memory
    now = time.time()

    if not HAS_PSUTIL:
        return None, None, None

    if now - last_update_time >= 3:  # Limit updates to once every 3 seconds to reduce overhead
        last_update_time = now

        # Detect OS
        is_windows = platform.system() == "Windows"
        is_linux = platform.system() == "Linux"

        # Get CPU usage (non-blocking)
        try:
            cached_cpu = psutil.cpu_percent(interval=0)
        except Exception:
            cached_cpu = None

        # Get memory usage
        try:
            cached_memory = psutil.virtual_memory().percent
        except Exception:
            cached_memory = None

        # Get CPU temperature
        cached_temp = None
        if is_linux:
            cached_temp = get_cpu_temp_linux()
            if cached_temp is None:
                try:
                    temps = psutil.sensors_temperatures()
                    if "coretemp" in temps:
                        cached_temp = temps["coretemp"][0].current
                except Exception:
                    cached_temp = None
        elif is_windows:
            try:
                temps = psutil.sensors_temperatures()
                if "cpu_thermal" in temps:
                    cached_temp = temps["cpu_thermal"][0].current
            except Exception:
                cached_temp = None

    return cached_temp, cached_cpu, cached_memory

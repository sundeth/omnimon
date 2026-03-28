import time


class ShakeDetector:
    def __init__(self, i2c_utils, threshold=1.5, cooldown=0.1):
        """
        Detects shakes based on directional changes rather than just exceeding a threshold.

        Args:
            i2c_utils: Utility for reading accelerometer data.
            threshold (float): Minimum G-force value to consider a shake.
            cooldown (float): Minimum time (seconds) between registered shakes.
        """
        self.i2c = i2c_utils
        self.threshold = threshold
        self.cooldown = cooldown
        
        self.last_shake_time = 0
        self.previous_x = None  # Track the previous acceleration value

    def check_for_shake(self):
        """Detects a shake when movement direction changes and exceeds threshold."""
        _, x, _ = self.i2c.read_accel()
        if x is None:
            return False

        now = time.time()
        
        # Check if acceleration exceeds threshold and direction flips
        if self.previous_x is not None and abs(x) > self.threshold:
            if (self.previous_x < 0 and x > 0) or (self.previous_x > 0 and x < 0):  # Movement switches direction
                if (now - self.last_shake_time) > self.cooldown:
                    self.last_shake_time = now
                    self.previous_x = x  # Update previous reading
                    return True

        self.previous_x = x  # Track last acceleration value
        return False
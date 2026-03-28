from datetime import datetime
import os

from core import constants


#=====================================================================
# GameConsole - Debug Logger
#=====================================================================

class GameConsole:
    """
    Simple console logger for debugging.
    Outputs timestamped messages only if debug mode is active.
    Also writes logs to a file if debug mode is enabled.
    """

    log_file = None

    @staticmethod
    def _init_log_file():
        """Initialize a new log file for this session if debug is enabled."""
        if GameConsole.log_file is None and constants.DEBUG_FILE_LOGGING:
            logs_dir = os.path.join(os.getcwd(), "logs")
            os.makedirs(logs_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_path = os.path.join(logs_dir, f"omnipet_{timestamp}.log")
            GameConsole.log_file = open(log_path, "w", encoding="utf-8")

    @staticmethod
    def log(message: str) -> None:
        """
        Logs a timestamped message to the console if debug mode is enabled.
        Also writes to a log file if debug mode is enabled.
        
        Args:
            message (str): Message to be logged.
        """
        if constants.DEBUG_MODE:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_line = f"[{timestamp}] {message}"
            print(log_line)
            if constants.DEBUG_FILE_LOGGING:
                GameConsole._init_log_file()
                if GameConsole.log_file:
                    GameConsole.log_file.write(log_line + "\n")

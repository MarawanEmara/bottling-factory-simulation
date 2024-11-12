import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
import coloredlogs


# ANSI color codes for terminal output
class Colors:
    HEADER = "\033[95m"
    INFO = "\033[94m"
    SUCCESS = "\033[92m"
    WARNING = "\033[93m"
    ERROR = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


class FactoryLogger:
    def __init__(self, name: str, log_file: Optional[str] = None):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # Create logs directory if it doesn't exist
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        # Default log file name using timestamp if none provided
        if log_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = f"logs/factory_{timestamp}.log"

        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)

        # Console handler with colors
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # Install colored logs
        coloredlogs.install(
            level="DEBUG",
            logger=self.logger,
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            level_styles={
                "debug": {"color": "white"},
                "info": {"color": "green"},
                "warning": {"color": "yellow"},
                "error": {"color": "red"},
                "critical": {"color": "red", "bold": True},
            },
        )

        # Add handlers
        self.logger.addHandler(file_handler)

        self.recent_logs = []  # Add this to store recent logs

    def _log(self, category: str, msg: str, level: str = "info"):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "message": msg,
            "level": level,
        }
        self.recent_logs.append(log_entry)
        self.recent_logs = self.recent_logs[-1000:]  # Keep last 1000 logs
        getattr(self.logger, level)(f"[{category}] {msg}")

    def get_recent_logs(self):
        return self.recent_logs

    def network(self, msg: str, level: str = "info"):
        """Log network-related messages"""
        self._log("NETWORK", msg, level)

    def modbus(self, msg: str, level: str = "info"):
        """Log Modbus-specific messages"""
        self._log("MODBUS", msg, level)

    def mqtt(self, msg: str, level: str = "info"):
        """Log MQTT-specific messages"""
        self._log("MQTT", msg, level)

    def opcua(self, msg: str, level: str = "info"):
        """Log OPC UA-specific messages"""
        self._log("OPC UA", msg, level)

    def process(self, msg: str, level: str = "info"):
        """Log process-related messages"""
        self._log("PROCESS", msg, level)

    def system(self, msg: str, level: str = "info"):
        """Log system-related messages"""
        self._log("SYSTEM", msg, level)


# Create a global logger instance
factory_logger = FactoryLogger("BottlingFactory")

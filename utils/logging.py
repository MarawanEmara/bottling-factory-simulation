import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
import coloredlogs

# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    INFO = '\033[94m'
    SUCCESS = '\033[92m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

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
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        
        # Console handler with colors
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Install colored logs
        coloredlogs.install(
            level='DEBUG',
            logger=self.logger,
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level_styles={
                'debug': {'color': 'white'},
                'info': {'color': 'green'},
                'warning': {'color': 'yellow'},
                'error': {'color': 'red'},
                'critical': {'color': 'red', 'bold': True},
            }
        )
        
        # Add handlers
        self.logger.addHandler(file_handler)
    
    def network(self, msg: str, level: str = "info"):
        """Log network-related messages"""
        getattr(self.logger, level)(f"[NETWORK] {msg}")
    
    def modbus(self, msg: str, level: str = "info"):
        """Log Modbus-specific messages"""
        getattr(self.logger, level)(f"[MODBUS] {msg}")
    
    def mqtt(self, msg: str, level: str = "info"):
        """Log MQTT-specific messages"""
        getattr(self.logger, level)(f"[MQTT] {msg}")
    
    def opcua(self, msg: str, level: str = "info"):
        """Log OPC UA-specific messages"""
        getattr(self.logger, level)(f"[OPC UA] {msg}")
    
    def process(self, msg: str, level: str = "info"):
        """Log process-related messages"""
        getattr(self.logger, level)(f"[PROCESS] {msg}")
    
    def system(self, msg: str, level: str = "info"):
        """Log system-related messages"""
        getattr(self.logger, level)(f"[SYSTEM] {msg}")

# Create a global logger instance
factory_logger = FactoryLogger("BottlingFactory")

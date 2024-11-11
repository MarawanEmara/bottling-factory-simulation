# devices/sensors.py

from abc import ABC, abstractmethod
import time
from typing import Any, Dict


class Sensor(ABC):
    def __init__(self, sensor_id: str, position: float):
        self.sensor_id = sensor_id
        self.position = position
        self.last_reading = None
        self.last_update = time.time()

    @abstractmethod
    def read(self) -> Dict[str, Any]:
        pass

    def update(self):
        """Update sensor reading"""
        self.last_reading = self.read()
        self.last_update = time.time()
        return self.last_reading


class ProximitySensor(Sensor):
    def __init__(self, sensor_id: str, position: float):
        super().__init__(sensor_id, position)
        self.detected = False

    def read(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "type": "proximity",
            "position": self.position,
            "detected": self.detected,
            "timestamp": time.time(),
        }


class LevelSensor(Sensor):
    def __init__(self, sensor_id: str, position: float):
        super().__init__(sensor_id, position)
        self.current_level = 0.0

    def read(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "type": "level",
            "position": self.position,
            "level": self.current_level,
            "timestamp": time.time(),
        }

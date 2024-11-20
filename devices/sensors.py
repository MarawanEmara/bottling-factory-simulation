# devices/sensors.py

from abc import ABC, abstractmethod
import time
from typing import Any, Dict
from network.monitor import protocol_monitor
from network.protocols import ModbusManager, MQTTManager
from utils.logging import factory_logger


class Sensor(ABC):
    def __init__(self, sensor_id: str, position: float):
        self.sensor_id = sensor_id
        self.position = position
        self.last_reading = None
        self.last_update = time.time()
        self.modbus_register = None
        # factory_logger.system(f"Initialized sensor {sensor_id} at position {position}")

    async def publish_reading(
        self, modbus_manager: ModbusManager, mqtt_manager: MQTTManager
    ):
        """Publish sensor reading through protocols"""
        reading = self.read()

        # Create a clean, JSON-serializable dictionary
        mqtt_data = {
            "sensor_id": self.sensor_id,
            "value": (
                reading.get("detected", False)
                if "detected" in reading
                else reading.get("level", 0.0)
            ),
            "timestamp": time.time(),
        }

        # Update Modbus register if configured
        if self.modbus_register is not None:
            value = 1 if reading.get("detected", False) else 0
            if "level" in reading:
                value = int(reading["level"] * 100)
            await modbus_manager.update_register(self.modbus_register, value)
            # factory_logger.system(
            #     f"Sensor {self.sensor_id} updated Modbus register {self.modbus_register} with value {value}"
            # )

        # Publish to MQTT
        await mqtt_manager.publish(f"factory/sensors/{self.sensor_id}", mqtt_data)
        # factory_logger.system(f"Sensor {self.sensor_id} published reading: {mqtt_data}")

        # Record protocol event
        protocol_monitor.record_event(
            "modbus", self.sensor_id, "plc", "sensor_reading", reading
        )

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
        # Map sensor IDs to Modbus registers
        register_map = {
            "proximity_entry": 1000,
            "proximity_pre_fill": 1001,
            "proximity_filling": 1002,
            "proximity_post_fill": 1003,
            "proximity_pre_cap": 1004,
            "proximity_capping": 1005,
            "proximity_post_cap": 1006,
            "proximity_pre_label": 1007,
            "proximity_labeling": 1008,
            "proximity_exit": 1009
        }
        self.modbus_register = register_map.get(sensor_id)
        if self.modbus_register is None:
            # factory_logger.system(f"Warning: No register mapped for sensor {sensor_id}", "warning")
            pass
        
        self.detected = False  # Initialize to False explicitly
        # factory_logger.system(
        #     f"Initialized proximity sensor {sensor_id} at position {position} with register {self.modbus_register}"
        # )

    def read(self) -> Dict[str, Any]:
        reading = {
            "sensor_id": self.sensor_id,
            "type": "proximity",
            "position": self.position,
            "detected": self.detected,
            "timestamp": time.time(),
        }
        if self.detected:
            # factory_logger.system(f"Proximity sensor {self.sensor_id} detected object")
            pass
        return reading


class LevelSensor(Sensor):
    def __init__(self, sensor_id: str, position: float):
        super().__init__(sensor_id, position)
        self.modbus_register = 2000  # Level sensor register
        self.current_level = 0.0
        # factory_logger.system(
        #     f"Initialized level sensor {sensor_id} with register {self.modbus_register}"
        # )

    def read(self) -> Dict[str, Any]:
        reading = {
            "sensor_id": self.sensor_id,
            "type": "level",
            "position": self.position,
            "level": self.current_level,
            "timestamp": time.time(),
        }
        if self.current_level > 0:
            # factory_logger.system(f"Level sensor {self.sensor_id} reading: {self.current_level:.1f}%")
            pass
        return reading

# devices/actuators.py

from abc import ABC, abstractmethod
import time
from typing import Any, Dict
from network.monitor import protocol_monitor
from network.protocols import ModbusManager, MQTTManager
from utils.logging import factory_logger


class Actuator(ABC):
    def __init__(self, actuator_id: str):
        self.actuator_id = actuator_id
        self.state = False
        self.last_activation = 0
        self.modbus_register = None
        # factory_logger.system(f"Initialized actuator {actuator_id}")

    @abstractmethod
    def activate(self):
        pass

    @abstractmethod
    def deactivate(self):
        pass

    def get_state(self) -> Dict[str, Any]:
        return {
            "actuator_id": self.actuator_id,
            "state": self.state,
            "last_activation": self.last_activation,
            "timestamp": time.time(),
        }

    async def publish_state(
        self, modbus_manager: ModbusManager, mqtt_manager: MQTTManager
    ):
        """Publish actuator state through protocols"""
        # Create a clean, JSON-serializable dictionary
        mqtt_data = {
            "actuator_id": self.actuator_id,
            "state": self.state,
            "last_activation": self.last_activation,
            "timestamp": time.time(),
        }

        if hasattr(self, "current_speed"):
            mqtt_data["speed"] = self.current_speed

        # Update Modbus register
        if self.modbus_register is not None:
            value = 1 if self.state else 0
            if hasattr(self, "current_speed"):
                value = int(self.current_speed * 100)
            await modbus_manager.update_register(self.modbus_register, value)
            # factory_logger.system(
            #     f"Actuator {self.actuator_id} updated Modbus register {self.modbus_register} with value {value}"
            # )

        # Publish to MQTT
        await mqtt_manager.publish(f"factory/actuators/{self.actuator_id}", mqtt_data)
        # factory_logger.system(
        #     f"Actuator {self.actuator_id} published state: {mqtt_data}"
        # )


class Valve(Actuator):
    def __init__(self, actuator_id: str):
        super().__init__(actuator_id)
        self.modbus_register = 2000
        # factory_logger.system(
        #     f"Initialized valve {actuator_id} with register {self.modbus_register}"
        # )

    def activate(self):
        if not self.state:
            self.state = True
            self.last_activation = time.time()
            # factory_logger.system(f"Valve {self.actuator_id} activated")

    def deactivate(self):
        if self.state:
            self.state = False
            # factory_logger.system(f"Valve {self.actuator_id} deactivated")


class ConveyorMotor(Actuator):
    def __init__(self, actuator_id: str, max_speed: float = 1.0):
        super().__init__(actuator_id)
        self.max_speed = max_speed
        self.current_speed = 0.0
        self.modbus_register = 2100  # Conveyor motor register

    def activate(self):
        self.state = True
        self.current_speed = self.max_speed
        self.last_activation = time.time()

    def deactivate(self):
        self.state = False
        self.current_speed = 0.0

    def set_speed(self, speed: float):
        self.current_speed = min(max(0.0, speed), self.max_speed)
        self.state = self.current_speed > 0


class CappingActuator(Actuator):
    def __init__(self, actuator_id: str):
        super().__init__(actuator_id)
        self.modbus_register = 2100
        # factory_logger.system(
        #     f"Initialized capping actuator {actuator_id} with register {self.modbus_register}"
        # )

    def activate(self):
        self.state = True
        self.last_activation = time.time()
        # factory_logger.system(f"Capping actuator {self.actuator_id} activated")

    def deactivate(self):
        self.state = False
        # factory_logger.system(f"Capping actuator {self.actuator_id} deactivated")


class LabelingMotor(Actuator):
    def __init__(self, actuator_id: str, max_speed: float = 1.0):
        super().__init__(actuator_id)
        self.max_speed = max_speed
        self.current_speed = 0.0
        self.modbus_register = 2200
        # factory_logger.system(
        #     f"Initialized labeling motor {actuator_id} with register {self.modbus_register}"
        # )

    def activate(self):
        self.state = True
        self.current_speed = self.max_speed
        self.last_activation = time.time()

    def deactivate(self):
        self.state = False
        self.current_speed = 0.0

    def set_speed(self, speed: float):
        previous_speed = self.current_speed
        self.current_speed = min(max(0.0, speed), self.max_speed)
        self.state = self.current_speed > 0
        # if self.current_speed != previous_speed:
        #     factory_logger.system(
        #         f"Labeling motor {self.actuator_id} speed changed from {previous_speed:.1f} to {self.current_speed:.1f}"
        #     )

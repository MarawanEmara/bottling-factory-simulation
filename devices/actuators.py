# devices/actuators.py

from abc import ABC, abstractmethod
import time
from typing import Any, Dict


class Actuator(ABC):
    def __init__(self, actuator_id: str):
        self.actuator_id = actuator_id
        self.state = False  # False = inactive, True = active
        self.last_activation = 0

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


class Valve(Actuator):
    def __init__(self, actuator_id: str, flow_rate: float = 1.0):
        super().__init__(actuator_id)
        self.flow_rate = flow_rate

    def activate(self):
        self.state = True
        self.last_activation = time.time()

    def deactivate(self):
        self.state = False


class ConveyorMotor(Actuator):
    def __init__(self, actuator_id: str, max_speed: float = 1.0):
        super().__init__(actuator_id)
        self.max_speed = max_speed
        self.current_speed = 0.0

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
        
    def activate(self):
        self.state = True
        self.last_activation = time.time()
        
    def deactivate(self):
        self.state = False


class LabelingMotor(Actuator):
    def __init__(self, actuator_id: str, max_speed: float = 1.0):
        super().__init__(actuator_id)
        self.max_speed = max_speed
        self.current_speed = 0.0
        
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

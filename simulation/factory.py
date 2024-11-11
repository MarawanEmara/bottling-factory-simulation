# simulation/factory.py

import time
from typing import Dict, List, Any
from queue import Queue
from threading import Thread, Event
import asyncio

from config.settings import SimulationConfig, FactoryLayout
from devices.sensors import ProximitySensor, LevelSensor, Sensor
from devices.actuators import (
    Valve,
    ConveyorMotor,
    CappingActuator,
    LabelingMotor,
    Actuator,
)


class BottlingFactory:
    def __init__(self):
        self.config = SimulationConfig()
        self.layout = FactoryLayout()

        # Initialize components
        self.sensors = self._init_sensors()
        self.actuators = self._init_actuators()

        # Production tracking
        self.bottles_produced = 0
        self.bottles_in_progress = Queue()

        # Control flags
        self.running = False
        self.stop_event = Event()

    def _init_sensors(self) -> Dict[str, Sensor]:
        """Initialize all sensors in the factory"""
        sensors = {}

        # Add proximity sensors
        for pos_name, position in self.layout.SENSOR_POSITIONS.items():
            sensor_id = f"proximity_{pos_name}"
            sensors[sensor_id] = ProximitySensor(sensor_id, position)

        # Add level sensor at filling station
        sensors["level_filling"] = LevelSensor(
            "level_filling", self.layout.STATION_POSITIONS["filling"]
        )

        return sensors

    def _init_actuators(self) -> Dict[str, Actuator]:
        """Initialize all actuators in the factory"""
        return {
            "main_conveyor": ConveyorMotor("main_conveyor"),
            "filling_valve": Valve("filling_valve"),
            "capping_actuator": CappingActuator("capping_actuator"),
            "labeling_motor": LabelingMotor("labeling_motor"),
        }

    async def start(self):
        """Start the factory simulation asynchronously"""
        if self.running:
            return

        self.running = True
        self.stop_event.clear()

        # Start the conveyor
        self.actuators["main_conveyor"].activate()

        # Run simulation in background task
        asyncio.create_task(self._run_simulation())

    async def stop(self):
        """Stop the factory simulation"""
        self.running = False
        self.stop_event.set()

        # Stop all actuators
        for actuator in self.actuators.values():
            actuator.deactivate()

    async def _run_simulation(self):
        """Main simulation loop"""
        last_bottle_time = time.time()

        while not self.stop_event.is_set():
            current_time = time.time()

            # Add new bottle if it's time
            if current_time - last_bottle_time >= self.config.BOTTLE_INTERVAL:
                self._add_new_bottle()
                last_bottle_time = current_time

            # Update sensor readings
            self._update_sensors()

            # Process bottles at stations
            await self._process_stations()

            # Simulate at specified speed
            await asyncio.sleep(0.1 / self.config.SIMULATION_SPEED)

    def _add_new_bottle(self):
        """Add a new bottle to the production line"""
        bottle = {
            "id": f"bottle_{self.bottles_produced}",
            "position": 0,
            "state": "new",
        }
        self.bottles_in_progress.put(bottle)
        self.bottles_produced += 1

    def _update_sensors(self):
        """Update all sensor readings"""
        for sensor in self.sensors.values():
            sensor.update()

    async def _process_stations(self):
        """Process bottles at each station"""
        # Implementation of station processing logic
        pass

    def get_status(self) -> Dict[str, Any]:
        """Get current factory status"""
        return {
            "running": self.running,
            "bottles_produced": self.bottles_produced,
            "bottles_in_progress": self.bottles_in_progress.qsize(),
            "sensor_readings": {
                sid: sensor.last_reading for sid, sensor in self.sensors.items()
            },
            "actuator_states": {
                aid: actuator.get_state() for aid, actuator in self.actuators.items()
            },
        }

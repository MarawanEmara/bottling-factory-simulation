# simulation/factory.py

import time
from typing import Dict, List, Any
from queue import Queue
from asyncio import Event
import asyncio

from config import Config
from devices.sensors import ProximitySensor, LevelSensor, Sensor
from devices.actuators import (
    Valve,
    ConveyorMotor,
    CappingActuator,
    LabelingMotor,
    Actuator,
)
from devices.handlers import DeviceHandler
from network.protocols import ModbusManager, OPCUAManager
from scada.system import SCADASystem
from simulation.process import BottlingProcess, Bottle, BottleState
from utils.logging import factory_logger
from network.monitor import protocol_monitor


class BottlingFactory:
    def __init__(self, config: Config, scada: SCADASystem, protocols: Dict):
        self.config = config
        self.simulation_config = config.simulation
        self.layout = config.layout
        self.scada = scada
        self.protocols = protocols
        self.modbus = protocols["modbus"]
        self.opcua = protocols["opcua"]

        # Initialize components
        self.sensors = self._init_sensors()
        self.actuators = self._init_actuators()

        # Initialize device handler with existing SCADA instance
        self.device_handler = DeviceHandler(
            scada=self.scada,
            modbus=self.modbus,
            opcua=self.opcua,
            config=self.simulation_config,
        )

        # Initialize process
        self.process = BottlingProcess(self, config, self.device_handler)

        # Production tracking
        self.bottles_produced = 0
        self.bottles_in_progress = Queue()
        self.running = False
        self.stop_event = Event()
        self.start_time = time.time()
        self.metrics = {"successful_bottles": 0, "failed_bottles": 0}

    def _init_sensors(self) -> Dict[str, Sensor]:
        """Initialize all sensors in the factory"""
        sensors = {}

        # Add proximity sensors
        for pos_name, position in self.layout.SENSOR_POSITIONS.items():
            sensor_id = f"proximity_{pos_name}"
            sensors[sensor_id] = ProximitySensor(sensor_id, position)

        # Add level sensor at filling station
        level_sensor = LevelSensor(
            "level_filling", self.layout.STATION_POSITIONS["filling"]
        )
        sensors["level_filling"] = level_sensor

        return sensors

    def _init_actuators(self) -> Dict[str, Actuator]:
        """Initialize all actuators in the factory"""
        return {
            "main_conveyor": ConveyorMotor("main_conveyor"),
            "filling_valve": Valve("filling_valve"),
            "capping_actuator": CappingActuator("capping_actuator"),
            "labeling_motor": LabelingMotor("labeling_motor"),
        }

    async def initialize(self):
        """Initialize factory components"""
        try:
            # Initialize device handler
            await self.device_handler.initialize()

            # Initialize process
            await self.process.initialize()

            factory_logger.system("Factory initialization complete")
        except Exception as e:
            factory_logger.system(f"Factory initialization error: {str(e)}", "error")
            raise

    async def start(self):
        """Start the factory simulation asynchronously"""
        if self.running:
            return

        self.running = True
        self.stop_event.clear()
        self.start_time = time.time()

        try:
            # Start the conveyor
            self.actuators["main_conveyor"].activate()

            # Run simulation in background task
            asyncio.create_task(self._run_simulation())

        except Exception as e:
            factory_logger.system(f"Error starting factory: {str(e)}", "error")
            self.running = False
            raise

    async def stop(self):
        """Stop the factory simulation"""
        self.running = False
        self.stop_event.set()

        # Stop all actuators
        for actuator in self.actuators.values():
            actuator.deactivate()

    async def _run_simulation(self):
        """Main simulation loop with protocol monitoring"""
        last_bottle_time = time.time()

        while not self.stop_event.is_set():
            current_time = time.time()

            # Add new bottle if it's time
            if (
                current_time - last_bottle_time
                >= self.simulation_config.BOTTLE_INTERVAL
            ):
                self._add_new_bottle()
                # Record MQTT event for new bottle
                protocol_monitor.record_event(
                    "mqtt",
                    "factory",
                    "scada",
                    "new_bottle",
                    {"bottle_id": f"bottle_{self.bottles_produced}"},
                )
                last_bottle_time = current_time

            # Process bottles at stations
            await self._process_stations()

            # Save packet captures periodically
            if self.bottles_produced % 10 == 0:  # Every 10 bottles
                self.modbus.capture.save()
                self.opcua.capture.save()

            await asyncio.sleep(0.1 / self.simulation_config.SIMULATION_SPEED)

    def _add_new_bottle(self):
        """Add a new bottle to the production line"""
        bottle = {
            "id": f"bottle_{self.bottles_produced}",
            "position": 0,
            "state": "new",
        }
        self.bottles_in_progress.put(bottle)
        self.bottles_produced += 1
        factory_logger.process(f"Added bottle {bottle['id']} to production line")

    def _update_sensors(self):
        """Update all sensor readings"""
        for sensor in self.sensors.values():
            sensor.update()

    async def _process_stations(self):
        """Process bottles at each station"""
        if not self.bottles_in_progress.empty():
            bottle_dict = self.bottles_in_progress.get()

            # Convert dictionary to Bottle dataclass
            bottle = Bottle(
                id=bottle_dict["id"],
                position=bottle_dict["position"],
                state=BottleState(bottle_dict["state"]),
            )

            # Process the bottle
            success = await self.process.process_bottle(bottle)

            # Update metrics
            if bottle.state == BottleState.COMPLETED:
                self.metrics["successful_bottles"] += 1
            elif bottle.state == BottleState.ERROR:
                self.metrics["failed_bottles"] += 1
                factory_logger.process(
                    f"Bottle {bottle.id} failed: {bottle.error}", "error"
                )

            # Convert back to dictionary and put back in queue if not completed
            if bottle.state not in [BottleState.COMPLETED, BottleState.ERROR]:
                bottle_dict = {
                    "id": bottle.id,
                    "position": bottle.position,
                    "state": bottle.state.value,
                    "error": getattr(bottle, "error", None),
                }
                self.bottles_in_progress.put(bottle_dict)

    def get_status(self) -> Dict[str, Any]:
        """Get current factory status"""
        return {
            "running": self.running,
            "bottles_produced": self.bottles_produced,
            "bottles_in_progress": self.bottles_in_progress.qsize(),
            "stations": {
                "filling": {
                    "busy": self.process.station_locks["filling"].locked(),
                    "level": (
                        self.sensors["level_filling"].last_reading.get("level", 0)
                        if self.sensors["level_filling"].last_reading
                        else 0
                    ),
                    "valve_state": self.actuators["filling_valve"].state,
                },
                "capping": {
                    "busy": self.process.station_locks["capping"].locked(),
                    "actuator_state": self.actuators["capping_actuator"].state,
                },
                "labeling": {
                    "busy": self.process.station_locks["labeling"].locked(),
                    "motor_speed": self.actuators["labeling_motor"].current_speed,
                },
            },
            "conveyor_speed": self.actuators["main_conveyor"].current_speed,
            "metrics": self.metrics,
        }

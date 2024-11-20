# simulation/process.py

from dataclasses import dataclass
from enum import Enum
import asyncio
from typing import Dict, Any
import time
from utils.logging import factory_logger


class BottleState(Enum):
    NEW = "new"
    WAITING_FILL = "waiting_fill"
    FILLING = "filling"
    FILLED = "filled"
    WAITING_CAP = "waiting_cap"
    CAPPING = "capping"
    CAPPED = "capped"
    WAITING_LABEL = "waiting_label"
    LABELING = "labeling"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class Bottle:
    id: str
    position: float = 0.0
    state: BottleState = BottleState.NEW
    fill_level: float = 0.0
    has_cap: bool = False
    has_label: bool = False
    entry_time: float = time.time()
    error: str = None


class BottlingProcess:
    def __init__(self, factory, config, device_handler):
        self.factory = factory
        self.config = config
        self.device_handler = device_handler
        self.bottles = {}
        self.station_locks = {
            "filling": asyncio.Lock(),
            "capping": asyncio.Lock(),
            "labeling": asyncio.Lock(),
        }

    async def initialize(self):
        """Initialize the bottling process"""
        try:
            # Initialize station locks
            self.station_locks = {
                "filling": asyncio.Lock(),
                "capping": asyncio.Lock(),
                "labeling": asyncio.Lock(),
            }
            
            # Clear any existing bottles
            self.bottles = {}
            
            factory_logger.process("Bottling process initialized")
            
        except Exception as e:
            factory_logger.process(f"Error initializing bottling process: {str(e)}", "error")
            raise

    async def process_bottle(self, bottle: Bottle):
        """Process a bottle through all stations"""
        try:
            factory_logger.process(
                f"Processing bottle {bottle.id} in state {bottle.state}"
            )

            # If bottle is in ERROR state, remove it from the line
            if bottle.state == BottleState.ERROR:
                return False

            # If bottle is new, start with filling
            if bottle.state == BottleState.NEW:
                bottle.state = BottleState.WAITING_FILL
                factory_logger.process(f"Bottle {bottle.id} waiting for filling")
                return True

            # Handle filling station
            if bottle.state == BottleState.WAITING_FILL:
                async with self.station_locks["filling"]:
                    try:
                        bottle.state = BottleState.FILLING
                        factory_logger.process(
                            f"Starting fill operation for bottle {bottle.id}"
                        )

                        # Simulate filling process
                        await asyncio.sleep(self.config.simulation.FILL_TIME)
                        bottle.fill_level = 100
                        bottle.state = BottleState.FILLED
                        factory_logger.process(
                            f"Bottle {bottle.id} filled successfully"
                        )
                        return True
                    except Exception as e:
                        factory_logger.process(
                            f"Filling error for bottle {bottle.id}: {str(e)}", "error"
                        )
                        bottle.state = BottleState.ERROR
                        bottle.error = str(e)
                        return False

            # Handle capping station
            if bottle.state == BottleState.FILLED:
                bottle.state = BottleState.WAITING_CAP
                return True

            if bottle.state == BottleState.WAITING_CAP:
                async with self.station_locks["capping"]:
                    try:
                        bottle.state = BottleState.CAPPING
                        factory_logger.process(
                            f"Starting cap operation for bottle {bottle.id}"
                        )

                        # Simulate capping process
                        await asyncio.sleep(self.config.simulation.CAP_TIME)
                        bottle.has_cap = True
                        bottle.state = BottleState.CAPPED
                        factory_logger.process(
                            f"Bottle {bottle.id} capped successfully"
                        )
                        return True
                    except Exception as e:
                        factory_logger.process(
                            f"Capping error for bottle {bottle.id}: {str(e)}", "error"
                        )
                        bottle.state = BottleState.ERROR
                        bottle.error = str(e)
                        return False

            # Handle labeling station
            if bottle.state == BottleState.CAPPED:
                bottle.state = BottleState.WAITING_LABEL
                return True

            if bottle.state == BottleState.WAITING_LABEL:
                async with self.station_locks["labeling"]:
                    try:
                        bottle.state = BottleState.LABELING
                        factory_logger.process(
                            f"Starting label operation for bottle {bottle.id}"
                        )

                        # Simulate labeling process
                        await asyncio.sleep(self.config.simulation.LABEL_TIME)
                        bottle.has_label = True
                        bottle.state = BottleState.COMPLETED
                        factory_logger.process(
                            f"Bottle {bottle.id} labeled successfully"
                        )
                        return True
                    except Exception as e:
                        factory_logger.process(
                            f"Labeling error for bottle {bottle.id}: {str(e)}", "error"
                        )
                        bottle.state = BottleState.ERROR
                        bottle.error = str(e)
                        return False

            return True

        except Exception as e:
            bottle.state = BottleState.ERROR
            bottle.error = str(e)
            factory_logger.process(
                f"Error processing bottle {bottle.id}: {str(e)}", "error"
            )
            return False

    async def _move_to_position(self, bottle: Bottle, target_position: float):
        """Move bottle to specified position"""
        while bottle.position < target_position:
            # Check conveyor status
            if not self.factory.actuators["main_conveyor"].state:
                await asyncio.sleep(0.1)
                continue

            # Calculate movement
            speed = self.factory.actuators["main_conveyor"].current_speed
            distance = speed * 0.1  # 100ms update interval

            # Update position
            bottle.position = min(bottle.position + distance, target_position)

            # Update proximity sensors
            self._update_proximity_sensors(bottle)

            await asyncio.sleep(0.1)

    async def _fill_bottle(self, bottle: Bottle) -> bool:
        async with self.station_locks["filling"]:
            try:
                factory_logger.process(
                    f"Starting fill operation for bottle {bottle.id}"
                )
                bottle.state = BottleState.WAITING_FILL

                # Notify Filling PLC about bottle detection (Modbus TCP)
                await self.device_handler.handle_sensor_data("proximity_filling", True)

                factory_logger.process("Waiting for PLC to start fill operation...")
                await self.device_handler.plcs["filling"].wait_for_operation(
                    "start_fill"
                )
                factory_logger.process("PLC started fill operation")

                bottle.state = BottleState.FILLING
                start_time = time.time()

                while bottle.fill_level < 100:
                    if time.time() - start_time > self.config.FILL_TIME * 1.5:
                        raise Exception("Fill timeout")

                    # Update fill level
                    bottle.fill_level += (100 / self.config.FILL_TIME) * 0.1

                    # Update level sensor
                    await self.device_handler.handle_sensor_data(
                        "level_filling", bottle.fill_level
                    )

                    await asyncio.sleep(0.1)

                # Wait for PLC to complete fill operation (OPC UA)
                await self.device_handler.plcs["filling"].wait_for_operation(
                    "fill_complete"
                )

                bottle.state = BottleState.FILLED
                return True

            except Exception as e:
                bottle.state = BottleState.ERROR
                bottle.error = f"Filling error: {str(e)}"
                factory_logger.error(f"Error filling bottle {bottle.id}: {str(e)}")
                return False

    async def _cap_bottle(self, bottle: Bottle) -> bool:
        async with self.station_locks["capping"]:
            try:
                bottle.state = BottleState.WAITING_CAP

                # Notify Capping PLC about bottle detection (Modbus TCP)
                await self.device_handler.handle_sensor_data("proximity_capping", True)

                # Wait for PLC to start cap operation (OPC UA)
                await self.device_handler.plcs["capping"].wait_for_operation(
                    "start_cap"
                )

                bottle.state = BottleState.CAPPING

                # Wait for capping to complete
                await asyncio.sleep(self.config.CAP_TIME)

                # Wait for PLC to complete cap operation (OPC UA)
                await self.device_handler.plcs["capping"].wait_for_operation(
                    "cap_complete"
                )

                bottle.has_cap = True
                bottle.state = BottleState.CAPPED
                return True

            except Exception as e:
                bottle.state = BottleState.ERROR
                bottle.error = f"Capping error: {str(e)}"
                factory_logger.error(f"Error capping bottle {bottle.id}: {str(e)}")
                return False

    async def _label_bottle(self, bottle: Bottle) -> bool:
        async with self.station_locks["labeling"]:
            try:
                bottle.state = BottleState.WAITING_LABEL

                # Notify Labeling PLC about bottle detection (Modbus TCP)
                await self.device_handler.handle_sensor_data("proximity_labeling", True)

                # Wait for PLC to start label operation (OPC UA)
                await self.device_handler.plcs["labeling"].wait_for_operation(
                    "start_label"
                )

                bottle.state = BottleState.LABELING

                # Wait for labeling to complete
                await asyncio.sleep(self.config.LABEL_TIME)

                # Wait for PLC to complete label operation (OPC UA)
                await self.device_handler.plcs["labeling"].wait_for_operation(
                    "label_complete"
                )

                bottle.has_label = True
                bottle.state = BottleState.LABELED
                return True

            except Exception as e:
                bottle.state = BottleState.ERROR
                bottle.error = f"Labeling error: {str(e)}"
                factory_logger.error(f"Error labeling bottle {bottle.id}: {str(e)}")
                return False

    def _update_proximity_sensors(self, bottle: Bottle):
        """Update proximity sensors based on bottle position"""
        for sensor_id, sensor in self.factory.sensors.items():
            if isinstance(sensor, ProximitySensor):
                # Check if bottle is within sensor range (±2 units)
                sensor.detected = abs(sensor.position - bottle.position) <= 2

    def get_status(self) -> Dict[str, Any]:
        """Get current process status"""
        return {
            "active_bottles": len(self.bottles),
            "bottles_by_state": {
                state.name: len([b for b in self.bottles.values() if b.state == state])
                for state in BottleState
            },
            "station_status": {
                "filling": self.station_locks["filling"].locked(),
                "capping": self.station_locks["capping"].locked(),
                "labeling": self.station_locks["labeling"].locked(),
            },
        }

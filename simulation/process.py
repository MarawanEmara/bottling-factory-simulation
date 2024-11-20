# simulation/process.py

from dataclasses import dataclass
from enum import Enum
import asyncio
from typing import Dict, Any
import time
from utils.logging import factory_logger
from devices.sensors import ProximitySensor


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
        self.config = config.simulation
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
            factory_logger.process(
                f"Error initializing bottling process: {str(e)}", "error"
            )
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

            # Handle state transitions and PLC communication
            match bottle.state:
                case BottleState.NEW:
                    bottle.state = BottleState.WAITING_FILL
                    return True

                case BottleState.WAITING_FILL:
                    async with self.station_locks["filling"]:
                        try:
                            factory_logger.process(
                                f"Starting fill operation for bottle {bottle.id}"
                            )

                            # Move bottle to filling position
                            bottle.position = self.factory.layout.STATION_POSITIONS[
                                "filling"
                            ]

                            # Start filling and monitor level
                            bottle.state = BottleState.FILLING
                            start_time = time.time()
                            bottle.fill_level = 0.0

                            while bottle.fill_level < 95.0:  # Fill until 95%
                                if (
                                    time.time() - start_time
                                    > self.config.FILL_TIME * 1.5
                                ):
                                    raise TimeoutError("Fill operation timed out")

                                # Increment fill level
                                fill_increment = (100.0 / self.config.FILL_TIME) * 0.1
                                bottle.fill_level += fill_increment

                                # Convert bottle to dictionary for queue
                                bottle_dict = {
                                    "id": bottle.id,
                                    "position": bottle.position,
                                    "state": bottle.state.value,
                                    "fill_level": bottle.fill_level,
                                }

                                # Update bottle in factory's queue
                                if not self.factory.bottles_in_progress.empty():
                                    self.factory.bottles_in_progress.get()
                                self.factory.bottles_in_progress.put(bottle_dict)

                                factory_logger.process(
                                    f"Bottle {bottle.id} fill level: {bottle.fill_level:.1f}%"
                                )
                                await asyncio.sleep(0.1)

                            # 3. Complete filling
                            bottle.state = BottleState.FILLED
                            factory_logger.process(
                                f"Fill operation completed for bottle {bottle.id}"
                            )
                            return True

                        except Exception as e:
                            factory_logger.process(
                                f"Filling error for bottle {bottle.id}: {str(e)}",
                                "error",
                            )
                            bottle.state = BottleState.ERROR
                            bottle.error = str(e)
                            return False

                case BottleState.FILLED:
                    bottle.state = BottleState.WAITING_CAP
                    return True

                case BottleState.WAITING_CAP:
                    async with self.station_locks["capping"]:
                        try:
                            factory_logger.process(
                                f"Starting capping operation for bottle {bottle.id}"
                            )

                            # Move bottle to capping position
                            bottle.position = self.factory.layout.STATION_POSITIONS[
                                "capping"
                            ]

                            # 1. Notify Capping PLC about bottle detection
                            await self.device_handler.handle_sensor_data(
                                "proximity_capping", True
                            )

                            # 2. Start capping operation
                            bottle.state = BottleState.CAPPING
                            start_time = time.time()

                            # 3. Simulate capping operation
                            cap_time = self.config.CAP_TIME
                            for _ in range(
                                int(cap_time * 10)
                            ):  # Update 10 times per second
                                # Update bottle in factory's queue
                                bottle_dict = {
                                    "id": bottle.id,
                                    "position": bottle.position,
                                    "state": bottle.state.value,
                                }

                                if not self.factory.bottles_in_progress.empty():
                                    self.factory.bottles_in_progress.get()
                                self.factory.bottles_in_progress.put(bottle_dict)

                                await asyncio.sleep(0.1)

                            if time.time() - start_time > cap_time * 1.5:
                                raise TimeoutError("Capping operation timed out")

                            # 4. Complete capping
                            bottle.has_cap = True
                            bottle.state = BottleState.CAPPED
                            factory_logger.process(
                                f"Capping completed for bottle {bottle.id}"
                            )
                            return True

                        except Exception as e:
                            factory_logger.process(
                                f"Capping error for bottle {bottle.id}: {str(e)}",
                                "error",
                            )
                            bottle.state = BottleState.ERROR
                            bottle.error = str(e)
                            return False

                case BottleState.CAPPED:
                    bottle.state = BottleState.WAITING_LABEL
                    return True

                case BottleState.WAITING_LABEL:
                    async with self.station_locks["labeling"]:
                        try:
                            factory_logger.process(
                                f"Starting labeling operation for bottle {bottle.id}"
                            )

                            # 1. Notify Labeling PLC about bottle detection
                            await self.device_handler.handle_sensor_data(
                                "proximity_labeling", True
                            )

                            # 2. Start labeling operation
                            bottle.state = BottleState.LABELING
                            start_time = time.time()

                            # 3. Simulate labeling operation
                            await asyncio.sleep(self.config.LABEL_TIME)

                            if time.time() - start_time > self.config.LABEL_TIME * 1.5:
                                raise TimeoutError("Labeling operation timed out")

                            # 4. Complete labeling
                            bottle.has_label = True
                            bottle.state = BottleState.COMPLETED
                            factory_logger.process(
                                f"Labeling completed for bottle {bottle.id}"
                            )
                            return True

                        except Exception as e:
                            factory_logger.process(
                                f"Labeling error for bottle {bottle.id}: {str(e)}",
                                "error",
                            )
                            bottle.state = BottleState.ERROR
                            bottle.error = str(e)
                            return False

                case BottleState.COMPLETED:
                    try:
                        # Update metrics
                        self.factory.metrics["successful_bottles"] += 1

                        # Calculate production time
                        production_time = time.time() - bottle.entry_time
                        factory_logger.process(
                            f"Bottle {bottle.id} completed successfully in {production_time:.1f} seconds"
                        )

                        # Notify exit sensor
                        await self.device_handler.handle_sensor_data(
                            "proximity_exit", True
                        )

                        # Remove bottle from production line
                        return (
                            False  # Returning False removes the bottle from the queue
                        )

                    except Exception as e:
                        factory_logger.process(
                            f"Error finalizing bottle {bottle.id}: {str(e)}", "error"
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

                # 1. Proximity sensor detects bottle (Modbus TCP)
                await self.device_handler.handle_sensor_data(
                    "proximity_filling", True, protocol="modbus"
                )

                # 2. Wait for PLC to signal start (OPC UA)
                bottle.state = BottleState.FILLING
                while True:
                    operation = await self.device_handler.plcs[
                        "filling"
                    ].read_operation()
                    if operation == "start_fill":
                        break
                    await asyncio.sleep(0.1)

                # 3. Monitor fill level
                start_time = time.time()
                while bottle.fill_level < 100:
                    if time.time() - start_time > self.config.FILL_TIME * 1.5:
                        raise Exception("Fill timeout")

                    # Update fill level through Modbus
                    bottle.fill_level += (100 / self.config.FILL_TIME) * 0.1
                    await self.device_handler.handle_sensor_data(
                        "level_filling", float(bottle.fill_level), protocol="modbus"
                    )
                    await asyncio.sleep(0.1)

                # 4. Wait for PLC to signal completion (OPC UA)
                while True:
                    operation = await self.device_handler.plcs[
                        "filling"
                    ].read_operation()
                    if operation == "fill_complete":
                        break
                    await asyncio.sleep(0.1)

                bottle.state = BottleState.FILLED
                return True

            except Exception as e:
                bottle.state = BottleState.ERROR
                bottle.error = f"Filling error: {str(e)}"
                factory_logger.process(
                    f"Error filling bottle {bottle.id}: {str(e)}", "error"
                )
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

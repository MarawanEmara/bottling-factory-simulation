# simulation/process.py

from dataclasses import dataclass
from enum import Enum
import asyncio
from typing import Dict, Any
import time


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
    def __init__(self, factory, config):
        self.factory = factory
        self.config = config
        self.bottles = {}
        self.station_locks = {
            "filling": asyncio.Lock(),
            "capping": asyncio.Lock(),
            "labeling": asyncio.Lock(),
        }

    async def process_bottle(self, bottle: Bottle):
        """Process a bottle through all stations"""
        try:
            # Move to filling station
            await self._move_to_position(
                bottle, self.config.STATION_POSITIONS["filling"]
            )

            # Filling process
            if await self._fill_bottle(bottle):
                # Move to capping station
                await self._move_to_position(
                    bottle, self.config.STATION_POSITIONS["capping"]
                )

                # Capping process
                if await self._cap_bottle(bottle):
                    # Move to labeling station
                    await self._move_to_position(
                        bottle, self.config.STATION_POSITIONS["labeling"]
                    )

                    # Labeling process
                    if await self._label_bottle(bottle):
                        # Move to exit
                        await self._move_to_position(
                            bottle, self.config.CONVEYOR_LENGTH
                        )
                        bottle.state = BottleState.COMPLETED

        except Exception as e:
            bottle.state = BottleState.ERROR
            bottle.error = str(e)

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

            # simulation/process.py (continued)

            # Update position
            bottle.position = min(bottle.position + distance, target_position)

            # Update proximity sensors
            self._update_proximity_sensors(bottle)

            await asyncio.sleep(0.1)

    async def _fill_bottle(self, bottle: Bottle) -> bool:
        """Fill bottle at filling station"""
        async with self.station_locks["filling"]:
            try:
                bottle.state = BottleState.WAITING_FILL

                # Check if filling station is ready
                if not self.factory.sensors["level_filling"].last_reading:
                    raise Exception("Level sensor not responding")

                # Start filling
                bottle.state = BottleState.FILLING
                self.factory.actuators["filling_valve"].activate()

                # Monitor fill level
                start_time = time.time()
                while bottle.fill_level < 100:
                    if time.time() - start_time > self.config.FILL_TIME * 1.5:
                        raise Exception("Fill timeout")

                    # Update fill level
                    bottle.fill_level += (100 / self.config.FILL_TIME) * 0.1

                    # Update level sensor
                    self.factory.sensors["level_filling"].current_level = (
                        bottle.fill_level
                    )

                    await asyncio.sleep(0.1)

                # Complete filling
                self.factory.actuators["filling_valve"].deactivate()
                bottle.state = BottleState.FILLED
                return True

            except Exception as e:
                bottle.state = BottleState.ERROR
                bottle.error = f"Filling error: {str(e)}"
                return False

    async def _cap_bottle(self, bottle: Bottle) -> bool:
        """Cap bottle at capping station"""
        async with self.station_locks["capping"]:
            try:
                bottle.state = BottleState.WAITING_CAP

                # Start capping
                bottle.state = BottleState.CAPPING
                self.factory.actuators["capping_actuator"].activate()

                # Wait for capping to complete
                await asyncio.sleep(self.config.CAP_TIME)

                # Complete capping
                self.factory.actuators["capping_actuator"].deactivate()
                bottle.has_cap = True
                bottle.state = BottleState.CAPPED
                return True

            except Exception as e:
                bottle.state = BottleState.ERROR
                bottle.error = f"Capping error: {str(e)}"
                return False

    async def _label_bottle(self, bottle: Bottle) -> bool:
        """Label bottle at labeling station"""
        async with self.station_locks["labeling"]:
            try:
                bottle.state = BottleState.WAITING_LABEL

                # Start labeling
                bottle.state = BottleState.LABELING
                self.factory.actuators["labeling_motor"].activate()

                # Wait for labeling to complete
                await asyncio.sleep(self.config.LABEL_TIME)

                # Complete labeling
                self.factory.actuators["labeling_motor"].deactivate()
                bottle.has_label = True
                bottle.state = BottleState.COMPLETED
                return True

            except Exception as e:
                bottle.state = BottleState.ERROR
                bottle.error = f"Labeling error: {str(e)}"
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

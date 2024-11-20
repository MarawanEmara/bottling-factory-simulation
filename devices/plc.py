from abc import ABC, abstractmethod
from typing import Dict, Any
from network.protocols import ModbusManager, OPCUAManager
from utils.logging import factory_logger
import asyncio
import time


class BasePLC(ABC):
    def __init__(
        self, name: str, modbus: ModbusManager, opcua: OPCUAManager, config=None
    ):
        self.name = name
        self.modbus = modbus
        self.opcua = opcua
        self.config = config
        self.status = "idle"
        self.variables = {}
        self.proximity_sensor_register = None
        self.level_sensor_register = None

    async def initialize(self):
        """Initialize PLC variables in OPC UA"""
        try:
            # Create variables with proper types
            self.variables["status"] = await self.opcua.create_variable(
                f"{self.name}_status", "idle", "String"
            )
            self.variables["operation"] = await self.opcua.create_variable(
                f"{self.name}_operation", "none", "String"
            )
            factory_logger.system(f"Initialized OPC UA variables for {self.name}")
        except Exception as e:
            factory_logger.system(
                f"Error initializing PLC variables: {str(e)}", "error"
            )
            raise

    async def update_status(self, status: str):
        """Update PLC status"""
        self.status = status
        await self.opcua.update_variable(f"{self.name}_status", status)

    async def update_operation(self, operation: str):
        """Update current operation"""
        await self.opcua.update_variable(f"{self.name}_operation", operation)

    async def handle_sensor_data(self, sensor_id: str, value: Any):
        """Handle incoming sensor data"""
        try:
            # Extract raw value from dictionary if needed
            if isinstance(value, dict):
                value = value.get("value", False)

            # Convert to proper type based on sensor type
            if sensor_id.startswith("proximity_"):
                typed_value = bool(value)
                if self.proximity_sensor_register:
                    await self.modbus.update_register(
                        self.proximity_sensor_register, 1 if typed_value else 0
                    )
            elif sensor_id.startswith("level_"):
                typed_value = float(value)
                if self.level_sensor_register:
                    await self.modbus.update_register(
                        self.level_sensor_register, int(typed_value * 100)
                    )
            else:
                return

            # Handle the properly typed value
            await self._handle_typed_sensor_data(sensor_id, typed_value)

        except Exception as e:
            factory_logger.system(f"Error handling sensor data: {str(e)}", "error")

    async def _handle_typed_sensor_data(self, sensor_id: str, value: Any):
        """Handle sensor data with proper typing"""
        if sensor_id == "proximity_filling":
            await self.start_filling()
        elif sensor_id == "level_filling":
            await self.monitor_level(value)

    async def start_filling(self):
        """Start filling operation"""
        await self.update_status("filling")
        await self.update_operation("start_fill")
        await self.modbus.update_register(self.valve_register, 1)  # Open valve

    async def monitor_level(self, level: float):
        """Monitor fill level"""
        if level >= 100:  # Full
            await self.modbus.update_register(self.valve_register, 0)  # Close valve
            await self.update_status("complete")
            await self.update_operation("fill_complete")

    async def wait_for_operation(self, operation: str, timeout: float = 10.0):
        """Wait for operation with timeout"""
        start_time = time.time()
        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Timeout waiting for operation {operation}")

            try:
                current_operation = await self.opcua.read_variable(
                    f"{self.name}_operation"
                )
                if current_operation == operation:
                    break
                await asyncio.sleep(0.1)
            except Exception as e:
                factory_logger.system(
                    f"Error waiting for operation {operation}: {str(e)}", "error"
                )
                raise

        factory_logger.system(f"Operation {operation} completed successfully")


class FillingPLC(BasePLC):
    def __init__(self, modbus: ModbusManager, opcua: OPCUAManager, config=None):
        super().__init__("filling_plc", modbus, opcua, config)
        self.proximity_sensor_register = 1000
        self.level_sensor_register = 1001
        self.valve_register = 2000
        self.current_level = 0.0

    async def handle_sensor_data(self, sensor_id: str, value: Any):
        """Handle incoming sensor data"""
        await super().handle_sensor_data(sensor_id, value)

        try:
            if sensor_id == "proximity_filling" and value:
                # Start filling operation
                await self.update_operation("start_fill")
                await self.modbus.update_register(self.valve_register, 1)
                self.current_level = 0.0
                factory_logger.system("Starting fill operation")

            elif sensor_id == "level_filling":
                try:
                    level = float(value)
                    self.current_level = level
                    factory_logger.system(f"Current fill level: {level:.1f}%")

                    if level >= 95.0:  # Tank nearly full
                        await self.update_operation("fill_complete")
                        await self.modbus.update_register(self.valve_register, 0)
                        factory_logger.system("Fill operation complete")
                except ValueError:
                    factory_logger.system(f"Invalid level value: {value}", "error")

        except Exception as e:
            factory_logger.system(f"Error in filling PLC: {str(e)}", "error")


class CappingPLC(BasePLC):
    def __init__(self, modbus: ModbusManager, opcua: OPCUAManager, config=None):
        super().__init__("capping_plc", modbus, opcua, config)
        self.proximity_sensor_register = 1100
        self.actuator_register = 2100

    async def handle_sensor_data(self, sensor_id: str, value: Any):
        """Handle incoming sensor data"""
        await super().handle_sensor_data(sensor_id, value)
        
        try:
            if sensor_id == "proximity_capping" and value:
                # Start capping operation
                await self.update_operation("start_cap")
                await self.modbus.update_register(self.actuator_register, 1)
                factory_logger.system("Starting cap operation")
                
                # Simulate capping time using config
                cap_time = self.config.CAP_TIME if self.config else 2.0
                await asyncio.sleep(cap_time)
                
                # Complete capping
                await self.update_operation("cap_complete")
                await self.modbus.update_register(self.actuator_register, 0)
                factory_logger.system("Cap operation complete")
                
        except Exception as e:
            factory_logger.system(f"Error in capping PLC: {str(e)}", "error")


class LabelingPLC(BasePLC):
    def __init__(self, modbus: ModbusManager, opcua: OPCUAManager, config=None):
        super().__init__("labeling_plc", modbus, opcua, config)
        self.proximity_sensor_register = 1200
        self.motor_register = 2200

    async def handle_sensor_data(self, sensor_id: str, value: Any):
        """Handle incoming sensor data"""
        await super().handle_sensor_data(sensor_id, value)
        
        try:
            if sensor_id == "proximity_labeling" and value:
                # Start labeling operation
                await self.update_operation("start_label")
                await self.modbus.update_register(self.motor_register, 1)
                factory_logger.system("Starting label operation")
                
                # Simulate labeling time
                await asyncio.sleep(self.config.LABEL_TIME)
                
                # Complete labeling
                await self.update_operation("label_complete")
                await self.modbus.update_register(self.motor_register, 0)
                factory_logger.system("Label operation complete")
                
        except Exception as e:
            factory_logger.system(f"Error in labeling PLC: {str(e)}", "error")


class ConveyorPLC(BasePLC):
    def __init__(self, modbus: ModbusManager, opcua: OPCUAManager, config=None):
        super().__init__("conveyor_plc", modbus, opcua, config)
        self.proximity_sensor_register = 1300
        self.motor_register = 2300

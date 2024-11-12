from abc import ABC, abstractmethod
from typing import Dict, Any
from network.protocols import ModbusManager, OPCUAManager
from utils.logging import factory_logger
import asyncio

class BasePLC(ABC):
    def __init__(self, name: str, modbus: ModbusManager, opcua: OPCUAManager):
        self.name = name
        self.modbus = modbus
        self.opcua = opcua
        self.status = "idle"
        self.variables = {}
        
    async def initialize(self):
        """Initialize PLC variables in OPC UA"""
        self.variables["status"] = await self.opcua.create_variable(
            f"{self.name}_status", "idle"
        )
        self.variables["operation"] = await self.opcua.create_variable(
            f"{self.name}_operation", "none"
        )
        
    async def update_status(self, status: str):
        """Update PLC status"""
        self.status = status
        await self.opcua.update_variable(f"{self.name}_status", status)
        
    async def update_operation(self, operation: str):
        """Update current operation"""
        await self.opcua.update_variable(f"{self.name}_operation", operation)
        
    @abstractmethod
    async def handle_sensor_data(self, sensor_id: str, value: Any):
        """Handle incoming sensor data"""
        pass

    async def wait_for_operation(self, operation: str):
        while True:
            current_operation = await self.opcua.read_variable(f"{self.name}_operation")
            if current_operation == operation:
                break
            await asyncio.sleep(0.1)

class FillingPLC(BasePLC):
    def __init__(self, modbus: ModbusManager, opcua: OPCUAManager):
        super().__init__("filling_plc", modbus, opcua)
        self.level_sensor_register = 1000
        self.valve_register = 2000
        
    async def handle_sensor_data(self, sensor_id: str, value: Any):
        if sensor_id == "proximity_filling":
            await self.start_filling()
        elif sensor_id == "level_filling":
            await self.monitor_level(value)
            
    async def start_filling(self):
        """Start filling operation"""
        await self.update_status("filling")
        await self.update_operation("start_fill")
        self.modbus.update_register(self.valve_register, 1)  # Open valve
        
    async def monitor_level(self, level: float):
        """Monitor fill level"""
        if level >= 100:  # Full
            self.modbus.update_register(self.valve_register, 0)  # Close valve
            await self.update_status("complete")
            await self.update_operation("fill_complete")

class CappingPLC(BasePLC):
    def __init__(self, modbus: ModbusManager, opcua: OPCUAManager):
        super().__init__("capping_plc", modbus, opcua)
        self.proximity_sensor_register = 1100
        self.actuator_register = 2100
        
    async def handle_sensor_data(self, sensor_id: str, value: Any):
        if sensor_id == "proximity_capping" and value:
            await self.start_capping()
            
    async def start_capping(self):
        """Start capping operation"""
        await self.update_status("capping")
        await self.update_operation("start_cap")
        self.modbus.update_register(self.actuator_register, 1)
        await asyncio.sleep(2)  # Simulate capping time
        self.modbus.update_register(self.actuator_register, 0)
        await self.update_status("complete")
        await self.update_operation("cap_complete")

class LabelingPLC(BasePLC):
    def __init__(self, modbus: ModbusManager, opcua: OPCUAManager):
        super().__init__("labeling_plc", modbus, opcua)
        self.proximity_sensor_register = 1200
        self.motor_register = 2200
        
    async def handle_sensor_data(self, sensor_id: str, value: Any):
        if sensor_id == "proximity_labeling" and value:
            await self.start_labeling()
            
    async def start_labeling(self):
        """Start labeling operation"""
        await self.update_status("labeling")
        await self.update_operation("start_label")
        self.modbus.update_register(self.motor_register, 1)
        await asyncio.sleep(1.5)  # Simulate labeling time
        self.modbus.update_register(self.motor_register, 0)
        await self.update_status("complete")
        await self.update_operation("label_complete")

class ConveyorPLC(BasePLC):
    def __init__(self, modbus: ModbusManager, opcua: OPCUAManager):
        super().__init__("conveyor_plc", modbus, opcua)
        self.proximity_sensor_register = 1300
        self.motor_register = 2300
        
    async def handle_sensor_data(self, sensor_id: str, value: Any):
        if sensor_id.startswith("proximity_"):
            await self.adjust_conveyor(value)
            
    async def adjust_conveyor(self, sensor_active: bool):
        """Adjust conveyor based on sensor readings"""
        if sensor_active:
            await self.update_status("running")
            self.modbus.update_register(self.motor_register, 1)
        else:
            await self.update_status("idle")
            self.modbus.update_register(self.motor_register, 0)

from typing import Dict, Any
from devices.plc import FillingPLC, CappingPLC, LabelingPLC, ConveyorPLC
from network.protocols import ModbusManager, OPCUAManager
from scada.system import SCADASystem
from utils.logging import factory_logger

class DeviceHandler:
    def __init__(self, scada: SCADASystem, modbus: ModbusManager, opcua: OPCUAManager):
        self.scada = scada
        self.modbus = modbus
        self.opcua = opcua
        self.plcs = {
            "filling": FillingPLC(modbus, opcua),
            "capping": CappingPLC(modbus, opcua),
            "labeling": LabelingPLC(modbus, opcua),
            "conveyor": ConveyorPLC(modbus, opcua)
        }

    async def initialize(self):
        """Initialize all PLCs"""
        for plc in self.plcs.values():
            await plc.initialize()

    async def handle_sensor_data(self, sensor_id: str, value: Any):
        """Handle incoming sensor data"""
        plc_name = self._get_plc_for_sensor(sensor_id)
        if plc_name:
            await self.plcs[plc_name].handle_sensor_data(sensor_id, value)
        await self.scada._handle_sensor_data({"sensor_id": sensor_id, "value": value})

    async def handle_actuator_command(self, actuator_id: str, command: str):
        """Handle actuator commands"""
        plc_name = self._get_plc_for_actuator(actuator_id)
        if plc_name:
            await self._execute_actuator_command(plc_name, actuator_id, command)
        await self.scada._handle_actuator_data({"actuator_id": actuator_id, "command": command})

    def _get_plc_for_sensor(self, sensor_id: str) -> str:
        if "filling" in sensor_id:
            return "filling"
        elif "capping" in sensor_id:
            return "capping"
        elif "labeling" in sensor_id:
            return "labeling"
        elif "conveyor" in sensor_id:
            return "conveyor"
        return ""

    def _get_plc_for_actuator(self, actuator_id: str) -> str:
        if "valve" in actuator_id:
            return "filling"
        elif "capping" in actuator_id:
            return "capping"
        elif "labeling" in actuator_id:
            return "labeling"
        elif "conveyor" in actuator_id:
            return "conveyor"
        return ""

    async def _execute_actuator_command(self, plc_name: str, actuator_id: str, command: str):
        plc = self.plcs[plc_name]
        if command == "activate":
            await plc.activate_actuator(actuator_id)
        elif command == "deactivate":
            await plc.deactivate_actuator(actuator_id)
        else:
            factory_logger.warning(f"Unknown command {command} for actuator {actuator_id}")

    async def process_modbus_data(self, register: int, value: int):
        """Process data from Modbus registers"""
        sensor_id = self._get_sensor_id_from_register(register)
        if sensor_id:
            await self.handle_sensor_data(sensor_id, value)

    def _get_sensor_id_from_register(self, register: int) -> str:
        # Map Modbus registers to sensor IDs
        register_map = {
            1000: "proximity_filling",
            1100: "proximity_capping",
            1200: "proximity_labeling",
            1300: "proximity_conveyor",
            2000: "level_filling"
        }
        return register_map.get(register, "")

    async def update_opcua_variables(self):
        """Update OPC UA variables with current PLC states"""
        for plc_name, plc in self.plcs.items():
            await self.opcua.update_variable(f"{plc_name}_status", plc.status)
            await self.opcua.update_variable(f"{plc_name}_operation", plc.current_operation) 
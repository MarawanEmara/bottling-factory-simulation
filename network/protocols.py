# network/protocols.py

import asyncio
from typing import Callable, Any
from utils.logging import factory_logger
from asyncua import Server as OPCUAServer, ua
import paho.mqtt.client as mqtt
from scapy.all import wrpcap, Ether, IP, TCP, Raw
from pathlib import Path
from pymodbus import pymodbus_apply_logging_config
import pymodbus.client as ModbusClient
from pymodbus import FramerType
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusSlaveContext,
    ModbusServerContext,
)
from pymodbus.server import StartAsyncTcpServer
import json


class PacketCapture:
    def __init__(self, capture_file: str):
        self.packets = []
        self.capture_file = Path("captures") / capture_file
        # Create captures directory if it doesn't exist
        self.capture_file.parent.mkdir(exist_ok=True)
        # Add packet count for periodic saving
        self.packet_count = 0
        self.MAX_PACKETS_BEFORE_SAVE = 1000

    def capture_packet(self, protocol: str, src: str, dst: str, data: Any):
        """Capture a network packet with proper encapsulation"""
        try:
            # Convert data to bytes if it isn't already
            if isinstance(data, dict):
                data = json.dumps(data).encode()
            elif not isinstance(data, bytes):
                data = str(data).encode()

            # Map protocols to ports
            protocol_ports = {"modbus": 502, "mqtt": 1883, "opcua": 4840}

            sport = protocol_ports.get(protocol, 0)
            dport = sport

            # Create proper packet structure
            packet = (
                Ether()
                / IP(src=src, dst=dst)
                / TCP(sport=sport, dport=dport)
                / Raw(load=data)
            )
            self.packets.append(packet)
            self.packet_count += 1

            # Automatically save if we've accumulated enough packets
            if self.packet_count >= self.MAX_PACKETS_BEFORE_SAVE:
                self.save()
                self.packet_count = 0

        except Exception as e:
            factory_logger.network(
                f"Error capturing {protocol} packet: {str(e)}", "error"
            )

    def save(self):
        """Save captured packets to file"""
        if self.packets:
            try:
                # Append to existing pcap if it exists
                wrpcap(str(self.capture_file), self.packets, append=True)
                factory_logger.network(
                    f"Saved {len(self.packets)} packets to {self.capture_file}"
                )
                # Clear packets after saving
                self.packets = []
            except Exception as e:
                factory_logger.network(
                    f"Error saving packet capture: {str(e)}", "error"
                )


class ModbusManager:
    def __init__(self, port: int):
        self.port = port
        self.running = False
        self.client = None
        self.server = None
        self.server_task = None
        self.client_task = None
        self.capture = PacketCapture("modbus_traffic.pcap")

        factory_logger.network(f"Initializing ModbusManager on port {self.port}")

        # Create datastore with larger address space
        self.store = ModbusSlaveContext(
            di=ModbusSequentialDataBlock(0, [0] * 10000),  # Discrete Inputs
            co=ModbusSequentialDataBlock(0, [0] * 10000),  # Coils
            hr=ModbusSequentialDataBlock(0, [0] * 10000),  # Holding Registers
            ir=ModbusSequentialDataBlock(0, [0] * 10000),  # Input Registers
        )
        self.context = ModbusServerContext(slaves=self.store, single=True)

    async def run_server(self):
        """Run Modbus server in separate task"""
        try:
            factory_logger.network(f"Starting Modbus server on port {self.port}")
            self.server = await StartAsyncTcpServer(
                context=self.context, address=("127.0.0.1", self.port)
            )
            factory_logger.network("Modbus server started successfully")

            # Keep server running
            while self.running:
                await asyncio.sleep(0.1)

        except Exception as e:
            factory_logger.network(f"Server error: {str(e)}", "error")
            raise

    async def run_client(self):
        """Run Modbus client in separate task"""
        try:
            factory_logger.network("Starting Modbus client...")
            self.client = ModbusClient.AsyncModbusTcpClient(
                "127.0.0.1", port=self.port, framer=FramerType.SOCKET
            )

            # Try to connect with retry
            retry_count = 0
            max_retries = 3

            while retry_count < max_retries:
                try:
                    await self.client.connect()
                    if self.client.connected:
                        factory_logger.network("Modbus client connected successfully")
                        self.capture.capture_packet(
                            "modbus", "127.0.0.1", "127.0.0.1", b"Client connected"
                        )
                        break
                except Exception as e:
                    retry_count += 1
                    factory_logger.network(
                        f"Connection attempt {retry_count} failed: {str(e)}"
                    )
                    if retry_count < max_retries:
                        await asyncio.sleep(1)
                    else:
                        raise Exception("Failed to connect after max retries")

            # Keep client running
            while self.running and self.client.connected:
                await asyncio.sleep(0.1)

        except Exception as e:
            factory_logger.network(f"Client error: {str(e)}", "error")
            raise

    async def start(self):
        """Start both server and client in separate tasks"""
        try:
            self.running = True

            # Start server task
            factory_logger.network("Creating server task")
            self.server_task = asyncio.create_task(self.run_server())

            # Verify server task is running
            await asyncio.sleep(2)
            if self.server_task.done():
                raise Exception(f"Server task failed: {self.server_task.exception()}")

            # Start client task
            factory_logger.network("Creating client task")
            self.client_task = asyncio.create_task(self.run_client())

            # Wait and verify both tasks
            await asyncio.sleep(1)

            if self.server_task.done():
                raise Exception(f"Server task failed: {self.server_task.exception()}")
            if self.client_task.done():
                raise Exception(f"Client task failed: {self.client_task.exception()}")

            if not self.client or not self.client.connected:
                raise Exception("Failed to establish Modbus connection")

            factory_logger.network("Modbus manager started successfully")

        except Exception as e:
            self.running = False
            factory_logger.network(f"Modbus startup error: {str(e)}", "error")

            # Cancel tasks
            if self.server_task and not self.server_task.done():
                self.server_task.cancel()
            if self.client_task and not self.client_task.done():
                self.client_task.cancel()

            # Wait for tasks to complete
            await asyncio.gather(
                *[
                    t
                    for t in [self.server_task, self.client_task]
                    if t and not t.done()
                ],
                return_exceptions=True,
            )

            raise

    async def stop(self):
        """Stop both server and client"""
        try:
            self.running = False

            # Cancel tasks
            if self.server_task:
                self.server_task.cancel()
            if self.client_task:
                self.client_task.cancel()

            # Wait for tasks to complete
            await asyncio.gather(
                *[t for t in [self.server_task, self.client_task] if t],
                return_exceptions=True,
            )

            # Close connections
            if self.client and self.client.connected:
                self.client.close()
                factory_logger.network("Modbus client stopped")
            if self.server:
                self.server.close()
                factory_logger.network("Modbus server stopped")

            # Save captured packets
            self.capture.save()

        except Exception as e:
            factory_logger.network(f"Error stopping Modbus: {str(e)}", "error")

    async def read_register(self, address: int):
        """Read from Modbus register"""
        if not self.running or not self.client.connected:
            return None

        try:
            result = await self.client.read_holding_registers(address, 1, slave=1)
            if result.isError():
                return None
            return result.registers[0] if hasattr(result, "registers") else None
        except Exception as e:
            factory_logger.network(
                f"Error reading register {address}: {str(e)}", "error"
            )
            return None

    async def update_register(self, register: int, value: int):
        """Update Modbus register and capture packet"""
        try:
            if self.client and self.client.connected:
                # Create Modbus packet data
                data = {
                    "function": "write_register",
                    "register": register,
                    "value": value
                }
                # Capture packet before sending
                self.capture.capture_packet(
                    "modbus",
                    "127.0.0.1",
                    "127.0.0.1",
                    data
                )
                await self.client.write_register(register, value)
        except Exception as e:
            factory_logger.network(f"Error updating register: {str(e)}", "error")


class MQTTManager:
    def __init__(self, broker: str, port: int):
        self.broker = broker
        self.port = port
        self.running = False
        self.client = mqtt.Client()
        self.capture = PacketCapture("mqtt_traffic.pcap")
        self.callbacks = {}
        self.loop = None

    async def start(self):
        try:
            # Store the event loop
            self.loop = asyncio.get_running_loop()

            # Set up message callback
            self.client.on_message = self._on_message

            # Add retry logic for MQTT connection
            retry_count = 0
            while retry_count < 3:
                try:
                    self.client.connect(self.broker, self.port)
                    self.client.loop_start()
                    self.running = True
                    factory_logger.network(
                        f"MQTT client connected to {self.broker}:{self.port}"
                    )
                    break
                except Exception:
                    retry_count += 1
                    await asyncio.sleep(1)

            if not self.running:
                raise Exception(
                    f"Failed to connect to MQTT broker at {self.broker}:{self.port}"
                )

        except Exception as e:
            factory_logger.network(f"MQTT error: {str(e)}", "error")
            self.running = False

    async def stop(self):
        """Stop MQTT client"""
        if self.running:
            self.client.loop_stop()
            self.client.disconnect()
            self.running = False

    async def subscribe(self, topic: str, callback: Callable):
        """Subscribe to MQTT topic with callback"""
        if self.running:
            self.callbacks[topic] = callback
            self.client.subscribe(topic)
            # Capture subscribe packet
            self.capture.capture_packet(
                "mqtt", "127.0.0.1", "127.0.0.1", bytes(f"SUB {topic}", "utf-8")
            )
            factory_logger.network(f"Subscribed to MQTT topic: {topic}")

    async def publish(self, topic: str, payload: Any):
        """Publish MQTT message and capture packet"""
        if self.running:
            try:
                # Capture packet before publishing
                self.capture.capture_packet(
                    "mqtt",
                    "127.0.0.1",
                    self.broker,
                    {
                        "topic": topic,
                        "payload": payload
                    }
                )
                self.client.publish(topic, str(payload))
            except Exception as e:
                factory_logger.network(f"MQTT publish error: {str(e)}", "error")

    def _on_message(self, client, userdata, message):
        """Handle incoming MQTT messages"""
        topic = message.topic
        try:
            # Extract value from dictionary if needed
            if isinstance(message.payload, dict):
                payload = message.payload.get("value", message.payload)
            else:
                payload = message.payload

            # Find matching callback
            for sub_topic, callback in self.callbacks.items():
                if mqtt.topic_matches_sub(sub_topic, topic):
                    try:
                        if self.loop and self.loop.is_running():
                            self.loop.create_task(callback(payload))
                    except Exception as e:
                        factory_logger.network(f"Callback error: {str(e)}", "error")

        except Exception as e:
            factory_logger.network(f"MQTT message processing error: {str(e)}", "error")


class OPCUAManager:
    def __init__(self):
        self.running = False
        self.server = None
        self.capture = PacketCapture("opcua_traffic.pcap")
        self.variables = {}
        self.namespace_idx = None

    async def start(self):
        """Start OPC UA server"""
        try:
            # Create server instance
            self.server = OPCUAServer()

            # Basic server setup
            await self.server.init()
            self.server.set_endpoint("opc.tcp://0.0.0.0:4840")

            # Set up namespace
            uri = "http://bottling.factory/opcua"
            self.namespace_idx = await self.server.register_namespace(uri)

            # Create root node
            root = self.server.nodes.objects
            factory_node = await root.add_object(self.namespace_idx, "BottlingFactory")

            # Start the server
            await self.server.start()

            self.running = True
            factory_logger.network("OPC UA server started successfully")

        except Exception as e:
            self.running = False
            factory_logger.network(f"OPC UA server startup error: {str(e)}", "error")
            if self.server:
                try:
                    await self.server.stop()
                except:
                    pass
            raise

    async def create_variable(self, name: str, initial_value: Any, var_type: str):
        """Create OPC UA variable with proper type"""
        if not self.running:
            return None

        try:
            # Map Python types to OPC UA types
            type_mapping = {
                "Boolean": ua.VariantType.Boolean,
                "Double": ua.VariantType.Double,
                "String": ua.VariantType.String,
            }

            # Get OPC UA type
            ua_type = type_mapping.get(var_type)
            if not ua_type:
                raise ValueError(f"Unsupported variable type: {var_type}")

            # Create variable node
            node = await self.server.nodes.objects.add_variable(
                ua.NodeId(name, self.server.nodes.objects.nodeid.NamespaceIndex),
                name,
                initial_value,
                ua_type,
            )
            self.variables[name] = node
            return node

        except Exception as e:
            factory_logger.network(
                f"Error creating OPC UA variable {name}: {str(e)}", "error"
            )
            return None

    async def update_variable(self, name: str, value: Any):
        """Update OPC UA variable value and capture packet"""
        if not self.running:
            return

        try:
            # Capture packet before updating
            self.capture.capture_packet(
                "opcua",
                "127.0.0.1",
                "127.0.0.1",
                {
                    "node": name,
                    "value": value
                }
            )
            
            # Extract value from dictionary if needed
            if isinstance(value, dict):
                value = value.get("value", False)

            # Determine and convert to proper type
            if name.startswith("proximity_"):
                value = bool(value)
                var_type = "Boolean"
            elif name.startswith("level_"):
                value = float(value)
                var_type = "Double"
            else:
                # Default string handling
                value = str(value)
                var_type = "String"

            if name not in self.variables:
                # Create new variable with determined type
                node = await self.create_variable(name, value, var_type)
                if not node:
                    return
            else:
                node = self.variables[name]

            await node.write_value(value)

        except Exception as e:
            factory_logger.network(
                f"Error updating OPC UA variable {name}: {str(e)}", "error"
            )

    async def read_variable(self, name: str) -> Any:
        """Read OPC UA variable value"""
        if not self.running:
            return None

        try:
            if name not in self.variables:
                return None

            node = self.variables[name]
            value = await node.read_value()
            return value

        except Exception as e:
            factory_logger.network(
                f"Error reading OPC UA variable {name}: {str(e)}", "error"
            )
            return None

    async def stop(self):
        """Stop OPC UA server"""
        if self.running:
            try:
                self.running = False
                if self.server:
                    await self.server.stop()
                factory_logger.network("OPC UA server stopped")
            except Exception as e:
                factory_logger.network(
                    f"Error stopping OPC UA server: {str(e)}", "error"
                )

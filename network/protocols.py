# network/protocols.py

import asyncio
from typing import Callable, Any
from utils.logging import factory_logger
from asyncua import Server as OPCUAServer
import paho.mqtt.client as mqtt
from scapy.all import wrpcap, Ether, IP, TCP, Raw
from pathlib import Path
from pymodbus import pymodbus_apply_logging_config, ModbusException
import pymodbus.client as ModbusClient
from pymodbus import FramerType
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusSlaveContext,
    ModbusServerContext,
)
from utils.logging import factory_logger
from pymodbus.server import StartAsyncTcpServer


class PacketCapture:
    def __init__(self, capture_file: str):
        self.packets = []
        self.capture_file = Path("captures") / capture_file
        # Create captures directory if it doesn't exist
        self.capture_file.parent.mkdir(exist_ok=True)

    def capture_packet(self, protocol: str, src: str, dst: str, data: bytes):
        """Capture a network packet with proper encapsulation"""
        try:
            # Convert hostname/port combinations to IP addresses
            src_ip = "127.0.0.1"  # Use localhost for simulation
            dst_ip = "127.0.0.1"  # Use localhost for simulation

            # Create proper packet structure
            packet = (
                Ether()
                / IP(src=src_ip, dst=dst_ip)
                / TCP(sport=502, dport=502)
                / Raw(load=data)
            )
            self.packets.append(packet)

        except Exception as e:
            factory_logger.network(f"Error capturing packet: {str(e)}", "error")

    def save(self):
        """Save captured packets to file"""
        if self.packets:
            try:
                wrpcap(str(self.capture_file), self.packets)
                factory_logger.network(
                    f"Saved {len(self.packets)} packets to {self.capture_file}"
                )
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

        pymodbus_apply_logging_config("DEBUG")
        factory_logger.network(f"Initializing ModbusManager on port {self.port}")

        # Create datastore
        self.store = ModbusSlaveContext(
            di=ModbusSequentialDataBlock(0, [0] * 100),
            co=ModbusSequentialDataBlock(0, [0] * 100),
            hr=ModbusSequentialDataBlock(0, [0] * 100),
            ir=ModbusSequentialDataBlock(0, [0] * 100),
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
            self.server_task = asyncio.create_task(self.run_server())

            # Wait for server to initialize
            await asyncio.sleep(2)

            # Start client task
            self.client_task = asyncio.create_task(self.run_client())

            # Wait for both tasks to be ready
            await asyncio.sleep(1)

            if not self.client or not self.client.connected:
                raise Exception("Failed to establish Modbus connection")

            factory_logger.network("Modbus manager started successfully")

        except Exception as e:
            self.running = False
            factory_logger.network(f"Modbus startup error: {str(e)}", "error")

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

    async def update_register(self, address: int, value: int):
        """Write to Modbus register"""
        if not self.running or not self.client.connected:
            return False

        try:
            result = await self.client.write_register(address, value, slave=1)
            return not result.isError() if hasattr(result, "isError") else False
        except Exception as e:
            factory_logger.network(
                f"Error writing to register {address}: {str(e)}", "error"
            )
            return False


class MQTTManager:
    def __init__(self, broker: str, port: int):
        self.broker = broker
        self.port = port
        self.running = False
        self.client = mqtt.Client()
        self.capture = PacketCapture("mqtt_traffic.pcap")
        self.callbacks = {}

    async def start(self):
        try:
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
            self.client.publish(topic, str(payload))
            # Capture MQTT packet
            self.capture.capture_packet(
                "mqtt",
                "127.0.0.1",
                "127.0.0.1",
                bytes(f"PUB {topic} {payload}", "utf-8"),
            )

    def _on_message(self, client, userdata, message):
        """Handle incoming MQTT messages"""
        topic = message.topic
        payload = message.payload.decode()

        # Find matching callback
        for sub_topic, callback in self.callbacks.items():
            if mqtt.topic_matches_sub(sub_topic, topic):
                # Convert payload to dict if possible
                try:
                    import json

                    payload = json.loads(payload)
                except:
                    pass

                # Create asyncio task for callback
                asyncio.create_task(callback(payload))


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

    async def create_variable(self, name: str, initial_value: Any):
        """Create OPC UA variable"""
        if not self.running:
            factory_logger.network(
                "Cannot create variable - OPC UA server not running", "error"
            )
            return None

        try:
            # Create variable under root node
            node = await self.server.nodes.objects.add_variable(
                f"ns={self.namespace_idx};s={name}", name, initial_value
            )
            self.variables[name] = node
            return node

        except Exception as e:
            factory_logger.network(
                f"Error creating OPC UA variable {name}: {str(e)}", "error"
            )
            return None

    async def update_variable(self, name: str, value: Any):
        """Update OPC UA variable value"""
        if not self.running:
            return

        try:
            if name not in self.variables:
                node = await self.create_variable(name, value)
                if not node:
                    return
            else:
                node = self.variables[name]
            await node.write_value(value)

        except Exception as e:
            factory_logger.network(
                f"Error updating OPC UA variable {name}: {str(e)}", "error"
            )

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

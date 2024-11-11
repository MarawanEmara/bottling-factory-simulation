import tkinter as tk
from tkinter import ttk
import asyncio
from datetime import datetime
from utils.logging import factory_logger


class FactoryDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Bottling Factory Dashboard")

        # Create main container
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Status indicators
        self.status_frame = ttk.LabelFrame(
            self.main_frame, text="System Status", padding="5"
        )
        self.status_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))

        self.modbus_status = ttk.Label(self.status_frame, text="Modbus: Disconnected")
        self.modbus_status.grid(row=0, column=0, padx=5)

        self.mqtt_status = ttk.Label(self.status_frame, text="MQTT: Disconnected")
        self.mqtt_status.grid(row=0, column=1, padx=5)

        self.opcua_status = ttk.Label(self.status_frame, text="OPC UA: Disconnected")
        self.opcua_status.grid(row=0, column=2, padx=5)

        # Log viewer
        self.log_frame = ttk.LabelFrame(
            self.main_frame, text="System Logs", padding="5"
        )
        self.log_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.log_text = tk.Text(self.log_frame, height=20, width=80)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Scrollbar for logs
        self.scrollbar = ttk.Scrollbar(
            self.log_frame, orient=tk.VERTICAL, command=self.log_text.yview
        )
        self.scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text["yscrollcommand"] = self.scrollbar.set

        # Start periodic updates
        self.update_logs()

    def update_status(self, protocol: str, connected: bool):
        """Update connection status indicators"""
        status_text = "Connected" if connected else "Disconnected"
        status_color = "green" if connected else "red"

        if protocol == "modbus":
            self.modbus_status.config(
                text=f"Modbus: {status_text}", foreground=status_color
            )
        elif protocol == "mqtt":
            self.mqtt_status.config(
                text=f"MQTT: {status_text}", foreground=status_color
            )
        elif protocol == "opcua":
            self.opcua_status.config(
                text=f"OPC UA: {status_text}", foreground=status_color
            )

    def add_log(self, message: str):
        """Add a new log message to the log viewer"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)

    def update_logs(self):
        """Periodic log update"""
        # Here you would implement reading from your log file
        # For now, we'll just schedule the next update
        self.root.after(1000, self.update_logs)


def launch_dashboard():
    root = tk.Tk()
    dashboard = FactoryDashboard(root)
    return root, dashboard

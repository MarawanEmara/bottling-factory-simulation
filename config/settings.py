class Config:
    def __init__(self):
        # Simulation settings
        self.simulation = SimulationConfig()
        self.layout = LayoutConfig()


class SimulationConfig:
    def __init__(self):
        # Timing settings (in seconds)
        self.FILL_TIME = 3.0
        self.CAP_TIME = 2.0
        self.LABEL_TIME = 2.5
        self.BOTTLE_INTERVAL = 2.0  # Time between new bottles
        self.SIMULATION_SPEED = 1.0  # 1.0 = real-time, 2.0 = 2x speed, etc.

        # Network settings
        self.MODBUS_PORT = 5020
        self.MQTT_BROKER = "localhost"
        self.MQTT_PORT = 1883


class LayoutConfig:
    def __init__(self):
        # Station positions (in arbitrary units)
        self.STATION_POSITIONS = {"filling": 10, "capping": 20, "labeling": 30}

        # Sensor positions
        self.SENSOR_POSITIONS = {
            "entry": 0,
            "pre_fill": 8,
            "filling": 10,
            "post_fill": 12,
            "pre_cap": 18,
            "capping": 20,
            "post_cap": 22,
            "pre_label": 28,
            "labeling": 30,
            "exit": 32,
        }

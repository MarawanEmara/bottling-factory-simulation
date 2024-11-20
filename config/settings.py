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
        self.BOTTLE_INTERVAL = 2.0
        self.SIMULATION_SPEED = 1.0

        # Network settings
        self.MODBUS_SERVER_PORT = 5020
        self.MODBUS_CLIENT_PORT = 5022
        self.MQTT_BROKER = "localhost"
        self.MQTT_PORT = 1883
        self.OPCUA_PORT = 4840
        self.MODBUS_SERVER_PORT_ALT = 5020


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

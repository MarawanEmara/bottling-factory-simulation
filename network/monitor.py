from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List
import asyncio

@dataclass
class ProtocolEvent:
    timestamp: datetime
    protocol: str
    source: str
    destination: str
    event_type: str
    data: Dict

class ProtocolMonitor:
    def __init__(self):
        self.events: List[ProtocolEvent] = []
        
    def record_event(self, protocol: str, source: str, destination: str, 
                    event_type: str, data: Dict):
        """Record a protocol event"""
        event = ProtocolEvent(
            timestamp=datetime.now(),
            protocol=protocol,
            source=source,
            destination=destination,
            event_type=event_type,
            data=data
        )
        self.events.append(event)
        
    def get_protocol_summary(self) -> Dict:
        """Get summary of protocol usage"""
        return {
            "modbus_events": len([e for e in self.events if e.protocol == "modbus"]),
            "mqtt_events": len([e for e in self.events if e.protocol == "mqtt"]),
            "opcua_events": len([e for e in self.events if e.protocol == "opcua"])
        }

# Create global monitor instance
protocol_monitor = ProtocolMonitor()

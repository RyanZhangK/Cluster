"""Serial port detection for the Cluster Flasher."""

from dataclasses import dataclass

import serial.tools.list_ports


@dataclass
class PortInfo:
    """Information about a detected serial port."""

    device: str        # e.g. /dev/ttyUSB0 or COM3
    description: str   # e.g. "USB Serial Device" or "CP2102N"
    hwid: str          # e.g. "USB VID:PID=10C4:EA60 SER=012345"

    def display_name(self) -> str:
        """Human-readable label for combo boxes."""
        return f"{self.device} — {self.description}"


def list_ports() -> list[PortInfo]:
    """Return all available serial ports."""
    ports = serial.tools.list_ports.comports()
    return [
        PortInfo(device=p.device, description=p.description, hwid=p.hwid)
        for p in sorted(ports, key=lambda p: p.device)
    ]

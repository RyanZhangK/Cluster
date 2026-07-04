#pragma once
#include <string>
#include <vector>

struct PortInfo {
    std::string device;       // e.g. /dev/ttyUSB0 or COM3
    std::string description;  // e.g. "CP2102N USB to UART Bridge"
    std::string display_name() const { return device + " \xe2\x80\x94 " + description; }
};

/// Enumerate available serial ports. Returns empty vector on failure.
std::vector<PortInfo> list_serial_ports();

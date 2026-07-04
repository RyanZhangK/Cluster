#include "serial_ports.hpp"
#include <algorithm>
#include <filesystem>
#include <fstream>

#ifdef _WIN32
#include <windows.h>
#include <setupapi.h>
#include <devguid.h>
#pragma comment(lib, "setupapi.lib")
#else
#include <dirent.h>
#endif

namespace fs = std::filesystem;

// ---- Helpers ----

static bool is_tty_device(const std::string& name) {
#ifdef _WIN32
    return name.rfind("COM", 0) == 0;
#else
    return name.rfind("ttyUSB", 0) == 0 || name.rfind("ttyACM", 0) == 0
        || name.rfind("ttyS", 0)   == 0;
#endif
}

#ifndef _WIN32
static std::string read_sysfs_attr(const std::string& devname, const std::string& attr) {
    std::string path = "/sys/class/tty/" + devname + "/device/" + attr;
    std::ifstream f(path);
    if (!f.is_open()) return {};
    std::string val;
    std::getline(f, val);
    // Trim trailing newline
    if (!val.empty() && val.back() == '\n') val.pop_back();
    return val;
}

static std::string resolve_product_name(const std::string& devname) {
    std::string name = read_sysfs_attr(devname, "product");
    if (!name.empty()) return name;
    // Try parent device
    name = read_sysfs_attr(devname, "../product");
    if (!name.empty()) return name;
    // Fallback: driver name
    std::string driver_sym = "/sys/class/tty/" + devname + "/device/driver";
    std::error_code ec;
    fs::path driver_path = fs::read_symlink(driver_sym, ec);
    if (!ec) return driver_path.filename().string();
    return {};
}
#endif

#ifdef _WIN32
static std::vector<PortInfo> list_ports_win32() {
    std::vector<PortInfo> ports;
    HDEVINFO dev_info = SetupDiGetClassDevsA(
        &GUID_DEVCLASS_PORTS, nullptr, nullptr, DIGCF_PRESENT);
    if (dev_info == INVALID_HANDLE_VALUE) return ports;

    SP_DEVINFO_DATA dev_data{};
    dev_data.cbSize = sizeof(dev_data);
    char buf[256];

    for (DWORD i = 0; SetupDiEnumDeviceInfo(dev_info, i, &dev_data); ++i) {
        // Get the port name from the registry
        HKEY hkey = SetupDiOpenDevRegKey(
            dev_info, &dev_data, DICS_FLAG_GLOBAL, 0, DIREG_DEV, KEY_READ);
        if (hkey == INVALID_HANDLE_VALUE) continue;

        DWORD size = sizeof(buf);
        DWORD type = REG_SZ;
        if (RegQueryValueExA(hkey, "PortName", nullptr, &type,
                             reinterpret_cast<LPBYTE>(buf), &size) == ERROR_SUCCESS) {
            std::string port_name(buf);
            if (is_tty_device(port_name)) {
                // Get friendly name / description
                char desc[256] = {};
                DWORD desc_size = sizeof(desc);
                SetupDiGetDeviceRegistryPropertyA(
                    dev_info, &dev_data, SPDRP_FRIENDLYNAME, nullptr,
                    reinterpret_cast<PBYTE>(desc), desc_size, nullptr);
                // Strip " (COMxx)" suffix if present
                std::string description(desc);
                auto paren = description.rfind(" (COM");
                if (paren != std::string::npos) description = description.substr(0, paren);
                if (description.empty()) description = "Serial Port";
                ports.push_back({port_name, description});
            }
        }
        RegCloseKey(hkey);
    }
    SetupDiDestroyDeviceInfoList(dev_info);
    std::sort(ports.begin(), ports.end(),
              [](const PortInfo& a, const PortInfo& b) { return a.device < b.device; });
    return ports;
}
#endif

#ifndef _WIN32
static std::vector<PortInfo> list_ports_linux() {
    std::vector<PortInfo> ports;
    const char* dev_dir = "/dev";
    DIR* dir = opendir(dev_dir);
    if (!dir) return ports;

    struct dirent* entry;
    while ((entry = readdir(dir)) != nullptr) {
        std::string name(entry->d_name);
        if (!is_tty_device(name)) continue;

        PortInfo info;
        info.device = std::string(dev_dir) + "/" + name;
        info.description = resolve_product_name(name);
        if (info.description.empty()) info.description = name;
        ports.push_back(info);
    }
    closedir(dir);
    std::sort(ports.begin(), ports.end(),
              [](const PortInfo& a, const PortInfo& b) { return a.device < b.device; });
    return ports;
}
#endif

// ---- Public API ----

std::vector<PortInfo> list_serial_ports() {
#ifdef _WIN32
    return list_ports_win32();
#else
    return list_ports_linux();
#endif
}

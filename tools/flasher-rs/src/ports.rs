//! Cross-platform serial port enumeration (replaces serial_ports.cpp).
use serialport::SerialPortType;

#[derive(Debug, Clone)]
pub struct PortInfo {
    pub device: String,
    pub description: String,
}

impl PortInfo {
    /// Matches flasher-cpp `display_name()`: "device — description" (em dash U+2014).
    pub fn display_name(&self) -> String {
        format!("{} \u{2014} {}", self.device, self.description)
    }
}

/// Enumerate available serial ports, filtered to ttyUSB/ttyACM/ttyS (Linux)
/// or COM* (Windows), sorted by device path. Empty vec on failure (parity with C++).
pub fn list_serial_ports() -> Vec<PortInfo> {
    let Ok(infos) = serialport::available_ports() else {
        return Vec::new();
    };
    let mut ports: Vec<PortInfo> = infos
        .into_iter()
        .filter(|p| is_serial_port_name(&p.port_name))
        .map(|p| {
            let fallback = p
                .port_name
                .rsplit('/')
                .next()
                .unwrap_or(&p.port_name)
                .to_string();
            let description = match p.port_type {
                SerialPortType::UsbPort(info) => info.product.unwrap_or(fallback),
                _ => fallback,
            };
            PortInfo {
                device: p.port_name,
                description,
            }
        })
        .collect();
    ports.sort_by(|a, b| a.device.cmp(&b.device));
    ports
}

fn is_serial_port_name(path: &str) -> bool {
    let name = std::path::Path::new(path)
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("");
    #[cfg(windows)]
    {
        name.starts_with("COM")
    }
    #[cfg(not(windows))]
    {
        name.starts_with("ttyUSB") || name.starts_with("ttyACM") || name.starts_with("ttyS")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    #[cfg(not(windows))]
    fn filters_tty_names_on_linux() {
        assert!(is_serial_port_name("/dev/ttyUSB0"));
        assert!(is_serial_port_name("/dev/ttyACM1"));
        assert!(is_serial_port_name("/dev/ttyS3"));
        assert!(!is_serial_port_name("/dev/sda1"));
        assert!(!is_serial_port_name("/dev/tty"));
        assert!(!is_serial_port_name(""));
    }

    #[test]
    fn display_name_matches_cpp_format() {
        let p = PortInfo {
            device: "/dev/ttyUSB0".into(),
            description: "CP2102N".into(),
        };
        assert_eq!(p.display_name(), "/dev/ttyUSB0 \u{2014} CP2102N");
    }
}

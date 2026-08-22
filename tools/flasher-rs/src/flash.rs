//! Firmware flashing via the espflash library (replaces flasher.cpp + esptool subprocess).
use std::fs;
use std::sync::mpsc::{Receiver, Sender, channel};
use std::thread;

use espflash::connection::{Connection, ResetAfterOperation, ResetBeforeOperation};
use espflash::flasher::Flasher;
use espflash::target::ProgressCallbacks;
use serialport::SerialPortType;

/// Raw firmware image offset (parity with C++ `write_flash 0x00000`).
const FLASH_OFFSET: u32 = 0x0000;

#[derive(Debug, Clone)]
pub struct FlashConfig {
    pub port: String,
    pub firmware_path: String,
    pub baud: u32,
    pub erase_all: bool,
}

#[derive(Debug, Clone)]
pub enum FlashEvent {
    Log(String),
    /// Fraction 0.0..=1.0
    Progress(f32),
    Done(bool),
}

struct ChannelProgress {
    tx: Sender<FlashEvent>,
    total: usize,
}

impl ProgressCallbacks for ChannelProgress {
    fn init(&mut self, _addr: u32, total: usize) {
        self.total = total.max(1);
        let _ = self.tx.send(FlashEvent::Log(format!(
            "[INFO] 正在写入固件（{} bytes）...",
            self.total
        )));
    }
    fn update(&mut self, current: usize) {
        let pct = (current as f32 / self.total as f32).clamp(0.0, 1.0);
        let _ = self.tx.send(FlashEvent::Progress(pct));
    }
    fn verifying(&mut self) {
        let _ = self.tx.send(FlashEvent::Log("[INFO] 正在校验...".into()));
    }
    fn finish(&mut self, _skipped: bool) {}
}

/// Spawn the flash job on a background thread. Events arrive in order;
/// the channel closes once `Done` has been sent.
pub fn start_flash(cfg: FlashConfig) -> Receiver<FlashEvent> {
    let (tx, rx) = channel();
    thread::spawn(move || {
        let ok = run_flash(&cfg, &tx);
        let _ = tx.send(FlashEvent::Done(ok));
    });
    rx
}

fn run_flash(cfg: &FlashConfig, tx: &Sender<FlashEvent>) -> bool {
    macro_rules! log {
        ($($arg:tt)*) => {{ let _ = tx.send(FlashEvent::Log(format!($($arg)*))); }};
    }

    log!("[INFO] Starting flash...");

    // 1. Read firmware image
    let bin = match fs::read(&cfg.firmware_path) {
        Ok(b) => b,
        Err(e) => {
            log!("[ERROR] 无法读取固件文件 {}: {e}", cfg.firmware_path);
            return false;
        }
    };
    if bin.is_empty() {
        log!("[ERROR] 固件文件为空");
        return false;
    }

    // 2. Locate SerialPortInfo (espflash needs UsbPortInfo for its reset strategy)
    let info = match serialport::available_ports() {
        Ok(list) => list.into_iter().find(|p| p.port_name == cfg.port),
        Err(e) => {
            log!("[ERROR] 枚举串口失败: {e}");
            return false;
        }
    };
    let Some(info) = info else {
        log!("[ERROR] 串口不存在: {}", cfg.port);
        return false;
    };
    let usb_info = match info.port_type {
        SerialPortType::UsbPort(i) => i,
        _ => serialport::UsbPortInfo {
            vid: 0,
            pid: 0,
            serial_number: None,
            manufacturer: None,
            product: None,
        },
    };

    // 3. Open native port at 115200 — espflash syncs here first, then raises baud
    log!("[INFO] 正在连接 {} @ {} ...", cfg.port, cfg.baud);
    let serial = match serialport::new(&cfg.port, 115_200)
        .flow_control(serialport::FlowControl::None)
        .open_native()
    {
        Ok(s) => s,
        Err(e) => {
            log!("[ERROR] 打开串口失败: {e}");
            return false;
        }
    };

    let connection = Connection::new(
        serial,
        usb_info,
        ResetAfterOperation::HardReset,
        ResetBeforeOperation::DefaultReset,
        115_200,
    );

    // 4. Connect (RAM stub for fast writes, autodetect chip, raise baud afterwards)
    let mut flasher = match Flasher::connect(connection, true, false, false, None, Some(cfg.baud)) {
        Ok(f) => f,
        Err(e) => {
            log!("[ERROR] 连接芯片失败: {e}");
            return false;
        }
    };

    // 5. Optional full chip erase (--erase-all)
    if cfg.erase_all {
        log!("[INFO] 正在擦除全片...");
        if let Err(e) = flasher.erase_flash() {
            log!("[ERROR] 擦除失败: {e}");
            return false;
        }
    }

    // 6. Write raw image at offset 0x0000
    let mut cb = ChannelProgress {
        tx: tx.clone(),
        total: 0,
    };
    if let Err(e) = flasher.write_bin_to_flash(FLASH_OFFSET, &bin, &mut cb) {
        log!("[ERROR] 写入失败: {e}");
        return false;
    }

    log!("[DONE] Flash successful!");
    true
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::mpsc::channel;

    #[test]
    fn progress_callback_sends_clamped_fraction_in_order() {
        let (tx, rx) = channel();
        let mut cb = ChannelProgress { tx, total: 0 };
        cb.init(0x0000, 200);
        cb.update(100);
        cb.update(999_999);
        assert!(matches!(rx.recv(), Ok(FlashEvent::Log(_)))); // init logs write start
        assert!(matches!(rx.recv(), Ok(FlashEvent::Progress(p)) if (p - 0.5).abs() < 1e-6));
        assert!(matches!(rx.recv(), Ok(FlashEvent::Progress(p)) if p >= 1.0));
    }
}

//! UI application state + rendering. Owner: UI lane (plan Task 5).
//!
//! eframe 0.36 API: the required trait method is `ui(&mut self, &mut egui::Ui, &mut Frame)`
//! (there is no `update()`); the root `Ui` has no margin/background, so all content is
//! wrapped in an `egui::CentralPanel` shown via `show_inside`.
use std::collections::VecDeque;
use std::path::PathBuf;
use std::sync::mpsc::{Receiver, TryRecvError};
use std::time::Duration;

use eframe::egui;
use egui::{CornerRadius, Margin, RichText, Stroke, vec2};

use crate::flash::{FlashConfig, FlashEvent, start_flash};
use crate::ports::{PortInfo, list_serial_ports};
use crate::theme;

/// Baud list and order preserved exactly from `flasher-cpp/main.cpp`.
const BAUD_RATES: [u32; 5] = [460800, 115200, 921600, 230400, 74880];
/// Log buffer cap (oldest dropped), parity with C++.
const LOG_CAP: usize = 500;
const LABEL_WIDTH: f32 = 76.0;
const PORT_COMBO_WIDTH: f32 = 240.0;
const BAUD_COMBO_WIDTH: f32 = 120.0;
const FLASH_BUTTON_HEIGHT: f32 = 40.0;
const PROGRESS_HEIGHT: f32 = 8.0;
/// Repaint cadence while a flash is running so progress/log animate without input.
const REPAINT_INTERVAL: Duration = Duration::from_millis(50);

/// Mirrors C++ `FlashState`. Unlike the C++ binary, re-flashing after
/// Success/Failed is allowed (intentional fix recorded in the plan).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Phase {
    Idle,
    Flashing,
    Success,
    Failed,
}

pub struct App {
    ports: Vec<PortInfo>,
    selected_port: Option<usize>,
    firmware_path: Option<PathBuf>,
    /// Mirror of `firmware_path` for the read-only display field.
    firmware_display: String,
    baud_index: usize,
    erase_all: bool,
    phase: Phase,
    progress: f32,
    log_lines: VecDeque<String>,
    rx: Option<Receiver<FlashEvent>>,
}

impl App {
    pub fn new(_cc: &eframe::CreationContext<'_>) -> Self {
        let ports = list_serial_ports();
        let selected_port = (!ports.is_empty()).then_some(0);
        Self {
            ports,
            selected_port,
            firmware_path: None,
            firmware_display: String::new(),
            baud_index: 0,
            erase_all: false,
            phase: Phase::Idle,
            progress: 0.0,
            log_lines: VecDeque::new(),
            rx: None,
        }
    }

    /// Re-flash allowed whenever not currently flashing (intentional fix over C++,
    /// whose button went permanently dead after the first attempt).
    fn can_flash(&self) -> bool {
        self.phase != Phase::Flashing
            && self.selected_port.is_some()
            && self.firmware_path.is_some()
    }

    fn push_log(&mut self, line: impl Into<String>) {
        self.log_lines.push_back(line.into());
        while self.log_lines.len() > LOG_CAP {
            self.log_lines.pop_front();
        }
    }

    fn refresh_ports(&mut self) {
        self.ports = list_serial_ports();
        // Drop a selection that no longer exists, then seed the first port.
        if self.selected_port.is_some_and(|i| i >= self.ports.len()) {
            self.selected_port = None;
        }
        if self.selected_port.is_none() && !self.ports.is_empty() {
            self.selected_port = Some(0);
        }
    }

    fn start_flash(&mut self) {
        let (Some(index), Some(path)) = (self.selected_port, self.firmware_path.clone()) else {
            return;
        };
        let cfg = FlashConfig {
            port: self.ports[index].device.clone(),
            firmware_path: path.display().to_string(),
            baud: BAUD_RATES[self.baud_index],
            erase_all: self.erase_all,
        };
        self.rx = Some(start_flash(cfg));
        self.phase = Phase::Flashing;
        self.progress = 0.0;
        self.push_log("[INFO] Starting flash...");
    }

    /// Non-blocking drain of the flash thread's events. `Done` is sent last by the
    /// contract, so the receiver is dropped right after it and the background
    /// thread is already finished writing to the channel at that point.
    fn drain_events(&mut self) {
        let mut terminal = None;
        let mut new_logs: Vec<String> = Vec::new();
        if let Some(rx) = &self.rx {
            loop {
                match rx.try_recv() {
                    Ok(FlashEvent::Log(line)) => new_logs.push(line),
                    Ok(FlashEvent::Progress(fraction)) => {
                        self.progress = fraction.clamp(0.0, 1.0);
                    }
                    Ok(FlashEvent::Done(ok)) => {
                        terminal = Some(ok);
                        break;
                    }
                    Err(TryRecvError::Empty | TryRecvError::Disconnected) => break,
                }
            }
        }
        for line in new_logs {
            self.push_log(line);
        }
        if let Some(ok) = terminal {
            self.phase = if ok { Phase::Success } else { Phase::Failed };
            self.rx = None;
        }
    }

    fn row_label(ui: &mut egui::Ui, text: &str) {
        ui.add_sized(
            vec2(LABEL_WIDTH, ui.spacing().interact_size.y),
            egui::Label::new(text),
        );
    }

    fn port_row(&mut self, ui: &mut egui::Ui) {
        ui.horizontal(|ui| {
            Self::row_label(ui, "串口");
            if ui.button("刷新").clicked() {
                self.refresh_ports();
            }
            if self.ports.is_empty() {
                ui.weak("(未检测到串口)");
            } else {
                let preview = self
                    .selected_port
                    .and_then(|i| self.ports.get(i))
                    .map(|p| p.display_name())
                    .unwrap_or_else(|| "选择串口...".to_owned());
                egui::ComboBox::from_id_salt("port")
                    .width(PORT_COMBO_WIDTH)
                    .selected_text(preview)
                    .show_ui(ui, |ui| {
                        for (i, port) in self.ports.iter().enumerate() {
                            ui.selectable_value(
                                &mut self.selected_port,
                                Some(i),
                                port.display_name(),
                            );
                        }
                    });
            }
        });
    }

    fn firmware_row(&mut self, ui: &mut egui::Ui) {
        ui.horizontal(|ui| {
            Self::row_label(ui, "固件文件");
            let browse_width = 64.0;
            let field_width = ui.available_width() - browse_width - ui.spacing().item_spacing.x;
            ui.add_sized(
                vec2(field_width, ui.spacing().interact_size.y),
                egui::TextEdit::singleline(&mut self.firmware_display).interactive(false),
            );
            if ui.button("浏览").clicked()
                && let Some(path) = rfd::FileDialog::new()
                    .add_filter("Firmware", &["bin"])
                    .pick_file()
            {
                self.firmware_display = path.display().to_string();
                self.firmware_path = Some(path);
            }
        });
    }

    fn baud_row(&mut self, ui: &mut egui::Ui) {
        ui.horizontal(|ui| {
            Self::row_label(ui, "波特率");
            egui::ComboBox::from_id_salt("baud")
                .width(BAUD_COMBO_WIDTH)
                .selected_text(BAUD_RATES[self.baud_index].to_string())
                .show_ui(ui, |ui| {
                    for (i, baud) in BAUD_RATES.iter().enumerate() {
                        ui.selectable_value(&mut self.baud_index, i, baud.to_string());
                    }
                });
        });
    }

    fn erase_row(&mut self, ui: &mut egui::Ui) {
        ui.checkbox(&mut self.erase_all, "烧录前全片擦除 (--erase-all)");
    }

    fn flash_button_row(&mut self, ui: &mut egui::Ui) {
        let enabled = self.can_flash();
        let width = ui.available_width();
        let response = ui.add_enabled(
            enabled,
            egui::Button::new(RichText::new("开始烧录").strong())
                .min_size(vec2(width, FLASH_BUTTON_HEIGHT)),
        );
        if response.clicked() {
            self.start_flash();
        }
    }

    fn progress_and_status(&mut self, ui: &mut egui::Ui) {
        // Fill color per state, mirroring the C++ PlotHistogram overrides:
        // primary while flashing/idle, green on success, red on failure.
        let fill = match self.phase {
            Phase::Idle | Phase::Flashing => theme::PRIMARY,
            Phase::Success => theme::SUCCESS,
            Phase::Failed => theme::DANGER,
        };
        ui.add(
            egui::ProgressBar::new(self.progress)
                .desired_height(PROGRESS_HEIGHT)
                .corner_radius(CornerRadius::same(4))
                .fill(fill),
        );

        match self.phase {
            Phase::Idle => ui.weak("就绪"),
            Phase::Flashing => ui.label(RichText::new("正在烧录...").color(theme::TEXT)),
            Phase::Success => ui.label(RichText::new("烧录成功!").strong().color(theme::SUCCESS)),
            Phase::Failed => ui.label(
                RichText::new("烧录失败，请查看日志")
                    .strong()
                    .color(theme::DANGER),
            ),
        };
    }

    fn log_panel(&mut self, ui: &mut egui::Ui) {
        ui.strong("烧录日志");
        egui::Frame::new()
            .fill(theme::SURFACE)
            .corner_radius(CornerRadius::same(8))
            .stroke(Stroke::new(1.0, theme::BORDER_SOFT))
            .inner_margin(Margin::same(8))
            .show(ui, |ui| {
                egui::ScrollArea::vertical()
                    .auto_shrink(false)
                    .stick_to_bottom(true) // auto-scroll only when new lines arrive
                    .show(ui, |ui| {
                        for line in &self.log_lines {
                            ui.monospace(line.as_str());
                        }
                    });
            });
    }
}

impl eframe::App for App {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        self.drain_events();

        egui::CentralPanel::default()
            .frame(
                egui::Frame::new()
                    .fill(theme::BG)
                    .inner_margin(Margin::same(12)),
            )
            .show(ui, |ui| {
                ui.add(egui::Label::new(
                    RichText::new("Cluster Firmware Flasher").heading().strong(),
                ));
                ui.separator();

                self.port_row(ui);
                self.firmware_row(ui);
                self.baud_row(ui);
                self.erase_row(ui);
                self.flash_button_row(ui);
                self.progress_and_status(ui);
                self.log_panel(ui);
            });

        if self.phase == Phase::Flashing {
            ui.ctx().request_repaint_after(REPAINT_INTERVAL);
        }
    }
}

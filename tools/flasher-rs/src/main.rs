//! Cluster Firmware Flasher — entry point. Owner: UI lane (plan Task 5).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use eframe::egui;

use cluster_flasher::app::App;
use cluster_flasher::{fonts, theme};

fn main() -> eframe::Result<()> {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([600.0, 520.0])
            .with_title("Cluster Firmware Flasher"),
        ..Default::default()
    };

    eframe::run_native(
        "Cluster Firmware Flasher",
        options,
        Box::new(|cc| {
            theme::apply_dark_theme(&cc.egui_ctx);
            fonts::install_cjk_fonts(&cc.egui_ctx);
            Ok(Box::new(App::new(cc)))
        }),
    )
}

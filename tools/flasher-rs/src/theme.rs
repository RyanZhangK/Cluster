//! Dark theme translated 1:1 from `tools/flasher-cpp/theme.hpp`. Owner: UI lane (plan Task 4).
//!
//! Every color is pinned by the plan's Global Constraints table; do not "improve" them.
//! Mapping notes (egui 0.36): buttons and closed combo-boxes paint with
//! `widgets.<state>.weak_bg_fill`, inputs/progress track use `extreme_bg_color`,
//! child/popup surfaces use `widgets.noninteractive.bg_fill`.
use eframe::egui;
use egui::{Color32, CornerRadius, Margin, Stroke, vec2};

/// Window / panel background `#0f1117`.
pub const BG: Color32 = Color32::from_rgb(0x0f, 0x11, 0x17);
/// Child / popup surface `#161b27`.
pub const SURFACE: Color32 = Color32::from_rgb(0x16, 0x1b, 0x27);
/// Input / frame background `#1e2435`.
pub const FRAME: Color32 = Color32::from_rgb(0x1e, 0x24, 0x35);
/// Hovered frame `#2a3045`.
pub const FRAME_HOVER: Color32 = Color32::from_rgb(0x2a, 0x30, 0x45);
/// Primary blue `#4f6ef7`.
pub const PRIMARY: Color32 = Color32::from_rgb(0x4f, 0x6e, 0xf7);
/// Primary hover `#6b84f8`.
pub const PRIMARY_HOVER: Color32 = Color32::from_rgb(0x6b, 0x84, 0xf8);
/// Primary active `#3c58f7`.
pub const PRIMARY_ACTIVE: Color32 = Color32::from_rgb(0x3c, 0x58, 0xf7);
/// Success green `#22c55e`.
pub const SUCCESS: Color32 = Color32::from_rgb(0x22, 0xc5, 0x5e);
/// Danger red `#ef4444`.
pub const DANGER: Color32 = Color32::from_rgb(0xef, 0x44, 0x44);
/// Body text `#e2e8f0`.
pub const TEXT: Color32 = Color32::from_rgb(0xe2, 0xe8, 0xf0);
/// Disabled text `#8b95b0`.
pub const TEXT_DISABLED: Color32 = Color32::from_rgb(0x8b, 0x95, 0xb0);
/// Border `#2a3045` at 50% alpha (C++ `ImGuiCol_Border`).
pub const BORDER_SOFT: Color32 = Color32::from_rgba_unmultiplied_const(0x2a, 0x30, 0x45, 0x80);
/// Primary at 40% alpha (C++ `ImGuiCol_Header` selection tint).
pub const PRIMARY_TINT: Color32 = Color32::from_rgba_unmultiplied_const(0x4f, 0x6e, 0xf7, 0x66);

/// Apply the dark theme (colors + rounding + spacing) to both style variants.
pub fn apply_dark_theme(ctx: &egui::Context) {
    ctx.all_styles_mut(|style| {
        let visuals = &mut style.visuals;

        visuals.dark_mode = true;
        visuals.panel_fill = BG;
        visuals.window_fill = BG;
        visuals.window_corner_radius = CornerRadius::same(8);
        visuals.menu_corner_radius = CornerRadius::same(6);
        visuals.window_stroke = Stroke::new(1.0, BORDER_SOFT);

        // Text: body + disabled. (No `override_text_color` — it would clobber weak text.)
        visuals.weak_text_color = Some(TEXT_DISABLED);
        visuals.hyperlink_color = PRIMARY;
        visuals.faint_bg_color = FRAME;
        // Track of progress bars, inner background of text edits (C++ FrameBg).
        visuals.extreme_bg_color = FRAME;

        // Selection / header tint: primary at 40%, selected text stays body-colored.
        visuals.selection = egui::style::Selection {
            bg_fill: PRIMARY_TINT,
            stroke: Stroke::new(1.0, TEXT),
        };

        // Widget classes. Buttons + closed combo boxes paint `weak_bg_fill`,
        // generic frames paint `bg_fill`; set both so the palette is unambiguous.
        let class = |w: &mut egui::style::WidgetVisuals,
                     fill: Color32,
                     fg: Color32,
                     bg_stroke: Color32,
                     radius: u8| {
            w.bg_fill = fill;
            w.weak_bg_fill = fill;
            w.fg_stroke = Stroke::new(1.0, fg);
            w.bg_stroke = Stroke::new(1.0, bg_stroke);
            w.corner_radius = CornerRadius::same(radius);
        };

        class(
            &mut visuals.widgets.noninteractive,
            SURFACE,
            TEXT,
            BORDER_SOFT,
            6,
        );
        class(
            &mut visuals.widgets.inactive,
            PRIMARY,
            TEXT,
            Color32::TRANSPARENT,
            6,
        );
        class(
            &mut visuals.widgets.hovered,
            PRIMARY_HOVER,
            TEXT,
            Color32::TRANSPARENT,
            6,
        );
        class(
            &mut visuals.widgets.active,
            PRIMARY_ACTIVE,
            TEXT,
            Color32::TRANSPARENT,
            6,
        );
        // Combo box with its popup open (C++ TabHovered).
        class(&mut visuals.widgets.open, FRAME_HOVER, TEXT, BORDER_SOFT, 6);

        // Spacing (C++ WindowPadding / FramePadding / ItemSpacing / ScrollbarSize).
        let spacing = &mut style.spacing;
        spacing.item_spacing = vec2(10.0, 8.0);
        spacing.button_padding = vec2(10.0, 6.0);
        spacing.window_margin = Margin::same(12);
        spacing.menu_margin = Margin::same(12);
        spacing.scroll.bar_width = 10.0;
    });
}

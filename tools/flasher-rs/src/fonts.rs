//! CJK font loading. Owner: UI lane (plan Task 4).
//!
//! Appends a system Noto/WQY/YaHei face to the END of both font families, so the
//! built-in latin font keeps rendering latin glyphs crisply and the CJK face only
//! fills in the gaps. This replaces the C++ glyph-range hack in `main.cpp`
//! (including the hand-patched U+6D4F 浏 range).
use std::fs;

use eframe::egui;

/// Probe order mirrors `flasher-cpp/main.cpp`.
const FONT_CANDIDATES: &[&str] = &[
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/wenquanyi/wqy-microhei/wqy-microhei.ttc",
    "C:\\Windows\\Fonts\\msyh.ttc",
];

/// Install the first readable CJK font as a low-priority fallback.
/// Missing everywhere → leave egui defaults untouched.
pub fn install_cjk_fonts(ctx: &egui::Context) {
    let Some(bytes) = FONT_CANDIDATES.iter().find_map(|p| fs::read(p).ok()) else {
        return;
    };

    let mut fonts = egui::FontDefinitions::default();
    // `font_data` values are `Arc<FontData>` in egui 0.36 (verified in vendored epaint).
    fonts.font_data.insert(
        "cjk".to_owned(),
        std::sync::Arc::new(egui::FontData::from_owned(bytes)),
    );
    // Append at the END of each family so latin stays on the default font.
    // Monospace needs the fallback too, or Chinese log lines would render as tofu.
    for family in [egui::FontFamily::Proportional, egui::FontFamily::Monospace] {
        fonts
            .families
            .entry(family)
            .or_default()
            .push("cjk".to_owned());
    }
    ctx.set_fonts(fonts);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cjk_font_candidates_match_cpp_probe_order() {
        assert_eq!(
            FONT_CANDIDATES[0],
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"
        );
        assert_eq!(
            FONT_CANDIDATES[1],
            "/usr/share/fonts/wenquanyi/wqy-microhei/wqy-microhei.ttc"
        );
        assert_eq!(FONT_CANDIDATES[2], "C:\\Windows\\Fonts\\msyh.ttc");
    }

    #[test]
    fn install_is_noop_without_crash_on_headless() {
        // No font file may exist here; must simply return without panicking.
        let ctx = egui::Context::default();
        install_cjk_fonts(&ctx);
    }
}

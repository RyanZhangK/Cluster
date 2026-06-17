"""Theme styles for the Cluster Flasher UI.

Reuses the colour system from the main controller for visual consistency.
"""

# ─── 色彩系统（来自 controller/src/styles.py）────────────────────────────
C_BG = "#0f1117"
C_SURFACE = "#161b27"
C_CARD = "#1e2435"
C_BORDER = "#2a3045"
C_PRIMARY = "#4f6ef7"
C_PRIMARY_H = "#6b84f8"
C_SUCCESS = "#22c55e"
C_DANGER = "#ef4444"
C_WARNING = "#f59e0b"
C_TEXT = "#e2e8f0"
C_TEXT_SEC = "#8b95b0"
C_TEXT_MUTED = "#4a5270"


# ─── 样式工厂 ────────────────────────────────────────────────────────────


def btn_style(bg: str) -> str:
    return f"""
        QPushButton {{
            background-color: {bg};
            color: {C_TEXT};
            border: none;
            border-radius: 6px;
            padding: 6px 16px;
            font-weight: bold;
            font-size: 12px;
        }}
        QPushButton:hover {{ background-color: {bg}cc; }}
        QPushButton:pressed {{ background-color: {bg}99; }}
        QPushButton:disabled {{
            background-color: {C_BORDER};
            color: {C_TEXT_MUTED};
        }}
    """


def combo_style() -> str:
    return f"""
        QComboBox {{
            background-color: {C_SURFACE};
            color: {C_TEXT};
            border: 1px solid {C_BORDER};
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 12px;
        }}
        QComboBox:hover {{ border-color: {C_PRIMARY}; }}
        QComboBox::drop-down {{ border: none; }}
        QComboBox QAbstractItemView {{
            background-color: {C_CARD};
            color: {C_TEXT};
            border: 1px solid {C_BORDER};
            selection-background-color: {C_PRIMARY};
        }}
    """


def input_style() -> str:
    return f"""
        QLineEdit {{
            background-color: {C_SURFACE};
            color: {C_TEXT};
            border: 1px solid {C_BORDER};
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 12px;
        }}
        QLineEdit:focus {{ border-color: {C_PRIMARY}; }}
        QLineEdit::placeholder {{ color: {C_TEXT_MUTED}; }}
    """


def progress_style(color: str, radius: int = 4) -> str:
    return f"""
        QProgressBar {{
            background-color: {C_BORDER};
            border-radius: {radius}px;
            border: none;
            height: 8px;
        }}
        QProgressBar::chunk {{
            background-color: {color};
            border-radius: {radius}px;
        }}
    """


def section_label_style() -> str:
    return f"""
        color: {C_TEXT_MUTED};
        font-size: 10px;
        font-weight: bold;
        letter-spacing: 1px;
        background: transparent;
    """


def log_area_style() -> str:
    return f"""
        QTextEdit {{
            background-color: {C_BG};
            color: {C_TEXT_SEC};
            border: 1px solid {C_BORDER};
            border-radius: 6px;
            padding: 8px;
            font-size: 11px;
            font-family: "JetBrains Mono", "Fira Code", monospace;
        }}
        QScrollBar:vertical {{
            background: {C_BG};
            width: 6px;
            border-radius: 3px;
        }}
        QScrollBar::handle:vertical {{
            background: {C_BORDER};
            border-radius: 3px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    """

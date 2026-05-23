"""Theme styles for the Cluster UI."""

# ─── 色彩系统 ─────────────────────────────────────────────────────────────────
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
C_SIDEBAR = "#0c0f1a"
C_NAV_HOVER = "#181d2e"
C_NAV_ACTIVE = "#1e2a4a"

TEAM_COLORS = {"A": "#ef4444", "B": "#3b82f6", "C": "#22c55e", "D": "#f59e0b"}


# ─── 样式工厂 ─────────────────────────────────────────────────────────────────


def section_label_style() -> str:
    return f"""
        color: {C_TEXT_MUTED};
        font-size: 10px;
        font-weight: bold;
        letter-spacing: 1px;
        background: transparent;
    """


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


def toggle_btn_style(active: bool) -> str:
    if active:
        return f"""
            QPushButton {{
                background-color: {C_PRIMARY};
                color: {C_TEXT};
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {C_PRIMARY_H}; }}
        """
    return f"""
        QPushButton {{
            background-color: {C_SURFACE};
            color: {C_TEXT_SEC};
            border: 1px solid {C_BORDER};
            border-radius: 6px;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {C_CARD};
            color: {C_TEXT};
            border-color: {C_PRIMARY}88;
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


def spinbox_style() -> str:
    return f"""
        QSpinBox {{
            background-color: {C_SURFACE};
            color: {C_TEXT};
            border: 1px solid {C_BORDER};
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 12px;
        }}
        QSpinBox:focus {{ border-color: {C_PRIMARY}; }}
        QSpinBox::up-button, QSpinBox::down-button {{
            background-color: {C_CARD};
            border: none;
            width: 16px;
        }}
        QSpinBox::up-arrow {{
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-bottom: 5px solid {C_TEXT};
        }}
        QSpinBox::down-arrow {{
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {C_TEXT};
        }}
    """


def table_style() -> str:
    return f"""
        QTableWidget {{
            background-color: {C_SURFACE};
            gridline-color: transparent;
            border: 1px solid {C_BORDER};
            border-radius: 8px;
            color: {C_TEXT};
            font-size: 13px;
        }}
        QTableWidget::item {{
            padding: 0 12px;
            border-bottom: 1px solid {C_BORDER};
        }}
        QTableWidget::item:selected {{
            background-color: {C_NAV_ACTIVE};
            color: {C_TEXT};
        }}
        QHeaderView::section {{
            background-color: {C_CARD};
            color: {C_TEXT_MUTED};
            padding: 8px 12px;
            border: none;
            border-bottom: 1px solid {C_BORDER};
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 1px;
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


def progress_style(color: str, radius: int = 4) -> str:
    return f"""
        QProgressBar {{
            background-color: {C_BORDER};
            border-radius: {radius}px;
            border: none;
        }}
        QProgressBar::chunk {{
            background-color: {color};
            border-radius: {radius}px;
        }}
    """

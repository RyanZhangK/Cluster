"""Reusable UI widgets."""

# ─── 复用组件 ─────────────────────────────────────────────────────────────────

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from .styles import (
    C_BORDER,
    C_CARD,
    C_NAV_ACTIVE,
    C_NAV_HOVER,
    C_PRIMARY,
    C_TEXT,
    C_TEXT_MUTED,
    C_TEXT_SEC,
    section_label_style,
)


class NavButton(QPushButton):
    def __init__(
        self, icon_text: str, label: str, parent: "QWidget | None" = None
    ) -> None:
        super().__init__(parent)
        self._icon_text = icon_text
        self._label = label
        self.setText(f"  {icon_text}  {label}")
        self.setCheckable(True)
        self.setFixedHeight(42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh()

    def setChecked(self, arg__1: bool) -> None:
        super().setChecked(arg__1)
        self._refresh()

    def _refresh(self) -> None:
        checked = self.isChecked()
        left = (
            f"border-left: 3px solid {C_PRIMARY};"
            if checked
            else "border-left: 3px solid transparent;"
        )
        bg = C_NAV_ACTIVE if checked else "transparent"
        color = C_TEXT if checked else C_TEXT_SEC
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {color};
                border: none;
                {left}
                padding: 0 18px;
                text-align: left;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {C_NAV_HOVER};
                color: {C_TEXT};
            }}
        """)


class StatusDot(QLabel):
    def __init__(
        self, color: str = C_TEXT_MUTED, parent: "QLabel | None" = None
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(8, 8)
        self._set(color)

    def set_color(self, color: str) -> None:
        self._set(color)

    def _set(self, color: str) -> None:
        self.setStyleSheet(f"background-color: {color}; border-radius: 4px;")


class Card(QFrame):
    def __init__(self, parent: "QFrame | None" = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {C_CARD};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
            }}
        """)


class SectionLabel(QLabel):
    def __init__(self, text: str, parent: "QLabel | None" = None) -> None:
        super().__init__(text, parent)
        self.setStyleSheet(f"""
            color: {C_TEXT_MUTED};
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 1px;
            padding: 14px 18px 4px 18px;
            background: transparent;
        """)


def add_section_label(layout: QVBoxLayout, text: str) -> None:
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(section_label_style())
    layout.addWidget(lbl)

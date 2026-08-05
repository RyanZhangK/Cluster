from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from .styles import (
    C_BG,
    C_DANGER,
    C_PRIMARY,
    C_SUCCESS,
    C_TEXT_MUTED,
    C_WARNING,
    btn_style,
    combo_style,
    input_style,
    table_style,
    toggle_btn_style,
)
from .widgets import Card


def build_node_page(parent: Any) -> QWidget:
    page = QWidget()
    page.setStyleSheet(f"background-color: {C_BG};")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(28, 24, 28, 24)
    layout.setSpacing(12)

    # 统计卡片行
    stats_row = QHBoxLayout()
    stats_row.setSpacing(12)
    parent._stat_val_total = stat_card(stats_row, "总节点", "0", C_PRIMARY)
    parent._stat_val_online = stat_card(stats_row, "在线", "0", C_SUCCESS)
    parent._stat_val_offline = stat_card(stats_row, "离线", "0", C_DANGER)

    # 场馆锁定卡片
    parent._venue_lock_card = Card()
    parent._venue_lock_card.setFixedSize(150, 76)
    vl = QVBoxLayout(parent._venue_lock_card)
    vl.setContentsMargins(16, 10, 16, 10)
    vl.setSpacing(2)

    venue_lock_label = QLabel("场馆锁定")
    venue_lock_label.setStyleSheet(
        f"color: {C_TEXT_MUTED}; font-size: 11px; background: transparent;"
    )

    parent._venue_lock_btn = QPushButton("解锁")
    parent._venue_lock_btn.setCheckable(True)
    parent._venue_lock_btn.setFixedHeight(30)
    parent._venue_lock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    parent._venue_lock_btn.setStyleSheet(toggle_btn_style(False))
    parent._venue_lock_btn.clicked.connect(parent._on_venue_lock_toggled)

    vl.addWidget(parent._venue_lock_btn)
    vl.addWidget(venue_lock_label)
    stats_row.addWidget(parent._venue_lock_card)

    stats_row.addStretch()
    layout.addLayout(stats_row)

    # 过滤行
    filter_row = QHBoxLayout()
    filter_row.setSpacing(8)
    parent._search_input = QLineEdit()
    parent._search_input.setPlaceholderText("搜索节点ID...")
    parent._search_input.setFixedHeight(34)
    parent._search_input.setStyleSheet(input_style())
    parent._search_input.textChanged.connect(parent._on_filter_changed)
    filter_row.addWidget(parent._search_input)

    parent._filter_type_combo = QComboBox()
    parent._filter_type_combo.addItems(["全部类型", "STA", "DET"])
    parent._filter_type_combo.setStyleSheet(combo_style())
    parent._filter_type_combo.setFixedWidth(100)
    parent._filter_type_combo.currentTextChanged.connect(parent._on_filter_changed)
    filter_row.addWidget(parent._filter_type_combo)

    parent._filter_status_combo = QComboBox()
    parent._filter_status_combo.addItems(["全部状态", "在线", "离线"])
    parent._filter_status_combo.setStyleSheet(combo_style())
    parent._filter_status_combo.setFixedWidth(100)
    parent._filter_status_combo.currentTextChanged.connect(parent._on_filter_changed)
    filter_row.addWidget(parent._filter_status_combo)

    parent._filter_team_combo = QComboBox()
    parent._filter_team_combo.addItems(["全部队伍", "A", "B", "C", "D", "未激活"])
    parent._filter_team_combo.setStyleSheet(combo_style())
    parent._filter_team_combo.setFixedWidth(100)
    parent._filter_team_combo.currentTextChanged.connect(parent._on_filter_changed)
    filter_row.addWidget(parent._filter_team_combo)

    filter_row.addStretch()
    layout.addLayout(filter_row)

    # 操作行
    act_row = QHBoxLayout()
    act_row.setSpacing(8)
    parent._select_all_btn = QPushButton("全选")
    parent._select_all_btn.setFixedHeight(36)
    parent._select_all_btn.setStyleSheet(btn_style(C_PRIMARY))
    parent._select_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    parent._select_all_btn.clicked.connect(parent._on_select_all)
    act_row.addWidget(parent._select_all_btn)

    parent._invert_select_btn = QPushButton("反选")
    parent._invert_select_btn.setFixedHeight(36)
    parent._invert_select_btn.setStyleSheet(btn_style(C_PRIMARY))
    parent._invert_select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    parent._invert_select_btn.clicked.connect(parent._on_invert_select)
    act_row.addWidget(parent._invert_select_btn)

    parent._reset_btn = QPushButton("重置选中节点")
    parent._reset_btn.setFixedHeight(36)
    parent._reset_btn.setStyleSheet(btn_style(C_WARNING))
    parent._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    parent._reset_btn.clicked.connect(parent._on_reset_btn_clicked)
    act_row.addWidget(parent._reset_btn)

    parent._reset_all_btn = QPushButton("重置全部")
    parent._reset_all_btn.setFixedHeight(36)
    parent._reset_all_btn.setStyleSheet(btn_style(C_DANGER))
    parent._reset_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    parent._reset_all_btn.clicked.connect(parent._on_reset_all_clicked)
    act_row.addWidget(parent._reset_all_btn)

    act_row.addStretch()
    layout.addLayout(act_row)

    # 表格
    parent._table = QTableWidget()
    parent._table.setColumnCount(len(parent.COLUMN_HEADERS))
    parent._table.setHorizontalHeaderLabels(parent.COLUMN_HEADERS)
    parent._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    parent._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    parent._table.setStyleSheet(table_style())
    layout.addWidget(parent._table)

    return page


def stat_card(parent_layout: Any, label: str, value: str, color: str) -> QLabel:
    card = Card()
    card.setFixedSize(130, 76)
    cl = QVBoxLayout(card)
    cl.setContentsMargins(16, 10, 16, 10)
    cl.setSpacing(2)
    val_lbl = QLabel(value)
    val_lbl.setStyleSheet(
        f"color: {color}; font-size: 26px; font-weight: bold; background: transparent;"
    )
    txt_lbl = QLabel(label)
    txt_lbl.setStyleSheet(
        f"color: {C_TEXT_MUTED}; font-size: 11px; background: transparent;"
    )
    cl.addWidget(val_lbl)
    cl.addWidget(txt_lbl)
    parent_layout.addWidget(card)
    return val_lbl

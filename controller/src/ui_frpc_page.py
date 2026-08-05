"""FRPC page builder — extracted from ui.py."""

import json
from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .config import FRPC_AUTH_TOKEN, FRPC_PROXIES, FRPC_SERVER_ADDR, FRPC_SERVER_PORT
from .styles import (
    C_BG,
    C_BORDER,
    C_DANGER,
    C_PRIMARY,
    C_SIDEBAR,
    C_SUCCESS,
    C_TEXT,
    C_TEXT_MUTED,
    C_TEXT_SEC,
    btn_style,
    combo_style,
    input_style,
    spinbox_style,
    table_style,
)
from .widgets import Card, StatusDot, add_section_label


def build_frpc_page(parent: Any) -> QWidget:
    page = QWidget()
    page.setStyleSheet(f"background-color: {C_BG};")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(28, 24, 28, 24)
    layout.setSpacing(16)

    # ── 状态卡片 ─────────────────────────────────────────────────────────────
    status_card = Card()
    sc_layout = QVBoxLayout(status_card)
    sc_layout.setContentsMargins(20, 16, 20, 18)
    sc_layout.setSpacing(12)

    status_row = QHBoxLayout()
    parent._frpc_status_dot = StatusDot(C_TEXT_MUTED)
    parent._frpc_status_label = QLabel("FRPC 已停止")
    parent._frpc_status_label.setStyleSheet(
        f"color: {C_TEXT_SEC}; font-size: 15px; font-weight: bold; background: transparent;"
    )
    status_row.addWidget(parent._frpc_status_dot)
    status_row.addSpacing(10)
    status_row.addWidget(parent._frpc_status_label)
    status_row.addStretch()
    sc_layout.addLayout(status_row)

    btn_row = QHBoxLayout()
    btn_row.setSpacing(10)
    parent._frpc_start_btn = QPushButton("启动")
    parent._frpc_start_btn.setFixedSize(100, 38)
    parent._frpc_start_btn.setStyleSheet(btn_style(C_SUCCESS))
    parent._frpc_start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    parent._frpc_start_btn.clicked.connect(parent._on_frpc_start)
    parent._frpc_stop_btn = QPushButton("停止")
    parent._frpc_stop_btn.setFixedSize(100, 38)
    parent._frpc_stop_btn.setStyleSheet(btn_style(C_DANGER))
    parent._frpc_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    parent._frpc_stop_btn.clicked.connect(parent._on_frpc_stop)
    parent._frpc_stop_btn.setEnabled(False)
    btn_row.addWidget(parent._frpc_start_btn)
    btn_row.addWidget(parent._frpc_stop_btn)
    btn_row.addStretch()
    sc_layout.addLayout(btn_row)
    layout.addWidget(status_card)

    # ── 服务器配置卡 ────────────────────────────────────────────────────────
    server_card = Card()
    svl = QVBoxLayout(server_card)
    svl.setContentsMargins(20, 16, 20, 18)
    svl.setSpacing(12)
    add_section_label(svl, "服务器配置")

    form_grid = QVBoxLayout()
    form_grid.setSpacing(8)

    for label, widget in [
        ("服务器地址", "_frpc_server_addr"),
        ("认证令牌", "_frpc_auth_token"),
    ]:
        row = QHBoxLayout()
        row.setSpacing(12)
        lbl = QLabel(label)
        lbl.setFixedWidth(72)
        lbl.setStyleSheet(
            f"color: {C_TEXT_SEC}; font-size: 12px; background: transparent;"
        )
        edit = QLineEdit()
        edit.setStyleSheet(input_style())
        setattr(parent, widget, edit)
        row.addWidget(lbl)
        row.addWidget(edit)
        form_grid.addLayout(row)

    port_row = QHBoxLayout()
    port_row.setSpacing(12)
    port_lbl = QLabel("服务器端口")
    port_lbl.setFixedWidth(72)
    port_lbl.setStyleSheet(
        f"color: {C_TEXT_SEC}; font-size: 12px; background: transparent;"
    )
    parent._frpc_server_port = QSpinBox()
    parent._frpc_server_port.setRange(1, 65535)
    parent._frpc_server_port.setValue(7000)
    parent._frpc_server_port.setStyleSheet(spinbox_style())
    port_row.addWidget(port_lbl)
    port_row.addWidget(parent._frpc_server_port)
    port_row.addStretch()
    form_grid.addLayout(port_row)

    svl.addLayout(form_grid)
    layout.addWidget(server_card)

    # ── 代理列表卡 ────────────────────────────────────────────────────────
    proxy_card = Card()
    pvl = QVBoxLayout(proxy_card)
    pvl.setContentsMargins(20, 16, 20, 18)
    pvl.setSpacing(12)
    add_section_label(pvl, "代理列表")

    # 代理表格
    parent._proxy_table = QTableWidget()
    parent._proxy_table.setColumnCount(5)
    parent._proxy_table.setHorizontalHeaderLabels(
        ["名称", "类型", "本地地址", "本地端口", "远程端口"]
    )
    parent._proxy_table.setSelectionBehavior(
        QAbstractItemView.SelectionBehavior.SelectRows
    )
    parent._proxy_table.setSelectionMode(
        QAbstractItemView.SelectionMode.SingleSelection
    )
    parent._proxy_table.setStyleSheet(table_style())
    parent._proxy_table.horizontalHeader().setSectionResizeMode(
        QHeaderView.ResizeMode.Stretch
    )
    parent._proxy_table.setShowGrid(False)
    parent._proxy_table.verticalHeader().setVisible(False)
    parent._proxy_table.setMaximumHeight(200)
    pvl.addWidget(parent._proxy_table)

    # 添加代理表单
    add_row = QHBoxLayout()
    add_row.setSpacing(8)
    parent._proxy_name_input = QLineEdit()
    parent._proxy_name_input.setPlaceholderText("名称")
    parent._proxy_name_input.setStyleSheet(input_style())
    parent._proxy_type_combo = QComboBox()
    parent._proxy_type_combo.addItems(["tcp", "udp"])
    parent._proxy_type_combo.setStyleSheet(combo_style())
    parent._proxy_type_combo.setFixedWidth(80)
    parent._proxy_local_ip = QLineEdit()
    parent._proxy_local_ip.setPlaceholderText("127.0.0.1")
    parent._proxy_local_ip.setStyleSheet(input_style())
    parent._proxy_local_port = QSpinBox()
    parent._proxy_local_port.setRange(1, 65535)
    parent._proxy_local_port.setValue(80)
    parent._proxy_local_port.setStyleSheet(spinbox_style())
    parent._proxy_remote_port = QSpinBox()
    parent._proxy_remote_port.setRange(1, 65535)
    parent._proxy_remote_port.setValue(8080)
    parent._proxy_remote_port.setStyleSheet(spinbox_style())
    add_row.addWidget(parent._proxy_name_input)
    add_row.addWidget(parent._proxy_type_combo)
    add_row.addWidget(parent._proxy_local_ip)
    add_row.addWidget(parent._proxy_local_port)
    add_row.addWidget(parent._proxy_remote_port)
    pvl.addLayout(add_row)

    proxy_btn_row = QHBoxLayout()
    proxy_btn_row.setSpacing(10)
    add_proxy_btn = QPushButton("+ 添加代理")
    add_proxy_btn.setFixedHeight(34)
    add_proxy_btn.setStyleSheet(btn_style(C_PRIMARY))
    add_proxy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    add_proxy_btn.clicked.connect(parent._on_add_proxy)
    del_proxy_btn = QPushButton("删除选中")
    del_proxy_btn.setFixedHeight(34)
    del_proxy_btn.setStyleSheet(btn_style(C_TEXT_MUTED))
    del_proxy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    del_proxy_btn.clicked.connect(parent._on_delete_proxy)
    proxy_btn_row.addWidget(add_proxy_btn)
    proxy_btn_row.addWidget(del_proxy_btn)
    proxy_btn_row.addStretch()
    pvl.addLayout(proxy_btn_row)

    layout.addWidget(proxy_card)

    # ── 日志输出卡 ────────────────────────────────────────────────────────
    log_card = Card()
    ll = QVBoxLayout(log_card)
    ll.setContentsMargins(20, 16, 20, 18)
    ll.setSpacing(10)
    add_section_label(ll, "日志输出")

    parent._frpc_log = QTextEdit()
    parent._frpc_log.setReadOnly(True)
    parent._frpc_log.setFont(QFont("Consolas, monospace", 9))
    parent._frpc_log.setStyleSheet(f"""
        QTextEdit {{
            background-color: {C_SIDEBAR};
            color: {C_TEXT};
            border: 1px solid {C_BORDER};
            border-radius: 6px;
            padding: 10px;
            font-family: 'Consolas', 'Monaco', monospace;
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
    """)
    ll.addWidget(parent._frpc_log)

    clear_btn_row = QHBoxLayout()
    clear_log_btn = QPushButton("清空日志")
    clear_log_btn.setFixedHeight(34)
    clear_log_btn.setStyleSheet(btn_style(C_TEXT_MUTED))
    clear_log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    clear_log_btn.clicked.connect(parent._frpc_log.clear)
    clear_btn_row.addWidget(clear_log_btn)
    clear_btn_row.addStretch()
    ll.addLayout(clear_btn_row)

    layout.addWidget(log_card, 1)

    # 加载已保存的配置
    load_frpc_config(parent)
    return page


def load_frpc_config(parent: Any) -> None:
    """从 frpc.conf 恢复配置，fallback 到 pydantic settings。
    如果配置文件不存在，则自动创建默认配置。"""
    from .frpc_manager import _frpc_config_path

    frpc_conf = _frpc_config_path()
    if frpc_conf.exists():
        try:
            data: dict[str, Any] = json.loads(frpc_conf.read_text(encoding="utf-8"))
            parent._frpc_server_addr.setText(str(data.get("server_addr", "")))
            parent._frpc_server_port.setValue(
                int(data.get("server_port", FRPC_SERVER_PORT))
            )
            parent._frpc_auth_token.setText(str(data.get("auth_token", "")))
            proxies = data.get("proxies", [])
            if isinstance(proxies, list):
                populate_proxy_table(
                    parent._proxy_table, cast(list[dict[str, Any]], proxies)
                )
                return
        except (json.JSONDecodeError, OSError):
            pass

    parent._frpc_server_addr.setText(FRPC_SERVER_ADDR)
    parent._frpc_server_port.setValue(FRPC_SERVER_PORT)
    parent._frpc_auth_token.setText(FRPC_AUTH_TOKEN)
    try:
        proxies = json.loads(FRPC_PROXIES)
    except (json.JSONDecodeError, TypeError):
        proxies = []
    assert isinstance(proxies, list)
    populate_proxy_table(parent._proxy_table, cast(list[dict[str, Any]], proxies))

    # 配置文件不存在时自动创建默认配置
    default_config = collect_frpc_config(parent)
    try:
        frpc_conf.parent.mkdir(parents=True, exist_ok=True)
        frpc_conf.write_text(
            json.dumps(default_config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def collect_frpc_config(parent: Any) -> dict[str, Any]:
    """从 UI 表单收集 frpc 配置。"""
    proxies: list[dict[str, Any]] = []
    for row in range(parent._proxy_table.rowCount()):
        name = parent._proxy_table.item(row, 0)
        ptype = parent._proxy_table.item(row, 1)
        lip = parent._proxy_table.item(row, 2)
        lport = parent._proxy_table.item(row, 3)
        rport = parent._proxy_table.item(row, 4)
        if name and ptype and lip and lport and rport:
            proxies.append(
                {
                    "name": name.text(),
                    "type": ptype.text(),
                    "local_ip": lip.text(),
                    "local_port": int(lport.text()),
                    "remote_port": int(rport.text()),
                }
            )
    return {
        "server_addr": parent._frpc_server_addr.text(),
        "server_port": parent._frpc_server_port.value(),
        "auth_token": parent._frpc_auth_token.text(),
        "proxies": proxies,
    }


def populate_proxy_table(
    proxy_table: QTableWidget,
    proxies: list[dict[str, Any]],
) -> None:
    """将代理列表填充到表格。"""
    proxy_table.setRowCount(0)
    for row, p in enumerate(proxies):
        proxy_table.insertRow(row)
        for col, key in enumerate(
            ["name", "type", "local_ip", "local_port", "remote_port"]
        ):
            val = str(p.get(key, ""))
            item = QTableWidgetItem(val)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setForeground(QColor(C_TEXT))
            proxy_table.setItem(row, col, item)
        proxy_table.setRowHeight(row, 32)

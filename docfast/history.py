"""Conversion History Manager and Recent Activity Hub for DocFAST.
Persists past conversions, tracks bytes saved / compression ratios, and provides
a sleek Liquid-Glass window with instant actions (Open, Show in Folder, Copy).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

from PySide6.QtCore import Qt, QPoint, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
                                QPushButton, QScrollArea, QVBoxLayout, QWidget)

from .util import human_size
from .window import GlassWindow


def _history_file() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "DocFAST"
    else:
        base = Path.home() / ".config" / "DocFAST"
    base.mkdir(parents=True, exist_ok=True)
    return base / "conversion_history.json"


def record_conversion(src: str | Path, outputs: list[str | Path], cat: str = ""):
    """Records a completed conversion entry."""
    src_p = Path(src)
    if not outputs:
        return

    out_p = Path(outputs[0])
    src_size = src_p.stat().st_size if src_p.exists() else 0
    out_size = out_p.stat().st_size if out_p.exists() else 0

    ratio = 0.0
    if src_size > 0:
        ratio = round(((src_size - out_size) / src_size) * 100, 1)

    entry = {
        "id": f"{int(time.time() * 1000)}",
        "time": time.time(),
        "time_str": time.strftime("%d/%m %H:%M"),
        "src_name": src_p.name,
        "src_path": str(src_p),
        "src_size": src_size,
        "out_name": out_p.name,
        "out_path": str(out_p),
        "out_size": out_size,
        "ratio": ratio,
        "cat": cat,
    }

    entries = load_history()
    entries.insert(0, entry)
    entries = entries[:50]  # keep last 50
    try:
        _history_file().write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def load_history() -> list[dict]:
    p = _history_file()
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return []


def clear_history():
    p = _history_file()
    if p.exists():
        p.write_text("[]", encoding="utf-8")


class RecentConversionsWindow(GlassWindow):
    """Liquid-Glass Hub showing recent conversion stats, savings, and quick actions."""

    def __init__(self, parent=None):
        super().__init__("📊 Conversões Recentes · DocFAST Activity Hub", size=(640, 520))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        entries = load_history()
        total_conv = len(entries)
        total_src = sum(e.get("src_size", 0) for e in entries)
        total_out = sum(e.get("out_size", 0) for e in entries)
        saved_bytes = max(0, total_src - total_out)

        # 1. Header Summary Card
        summary_card = QFrame()
        summary_card.setStyleSheet("background: rgba(90, 200, 255, 0.08); border: 1px solid rgba(90, 200, 255, 0.25); border-radius: 12px; padding: 12px;")
        sc_lay = QHBoxLayout(summary_card)

        # Stat 1: Total count
        col1 = QVBoxLayout()
        lbl1_num = QLabel(str(total_conv))
        lbl1_num.setStyleSheet("font-size: 16pt; font-weight: 800; color: #5ac8ff;")
        lbl1_txt = QLabel("Arquivos Convertidos")
        lbl1_txt.setObjectName("dim")
        col1.addWidget(lbl1_num)
        col1.addWidget(lbl1_txt)
        sc_lay.addLayout(col1)

        sc_lay.addSpacing(20)

        # Stat 2: Space saved
        col2 = QVBoxLayout()
        lbl2_num = QLabel(f"⚡ {human_size(saved_bytes)}")
        lbl2_num.setStyleSheet("font-size: 16pt; font-weight: 800; color: #8dffb8;")
        lbl2_txt = QLabel("Espaço em Disco Otimizado")
        lbl2_txt.setObjectName("dim")
        col2.addWidget(lbl2_num)
        col2.addWidget(lbl2_txt)
        sc_lay.addLayout(col2)

        sc_lay.addStretch(1)

        # Clear button
        if total_conv > 0:
            btn_clear = QPushButton("Limpar Histórico")
            btn_clear.setStyleSheet("padding: 6px 12px; background: rgba(255,255,255,0.08); border-radius: 8px; color: #94a3b8;")
            btn_clear.clicked.connect(self._do_clear)
            sc_lay.addWidget(btn_clear)

        self.body.addWidget(summary_card)
        self.body.addSpacing(8)

        # 2. Scrollable conversion list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        container = QWidget()
        self.c_lay = QVBoxLayout(container)
        self.c_lay.setContentsMargins(0, 0, 0, 0)
        self.c_lay.setSpacing(6)

        if not entries:
            lbl_empty = QLabel("Nenhuma conversão registrada recentemente.\nArraste arquivos e converta para acompanhar aqui!")
            lbl_empty.setAlignment(Qt.AlignCenter)
            lbl_empty.setStyleSheet("color: #64748b; font-size: 10pt; padding: 40px;")
            self.c_lay.addWidget(lbl_empty)
        else:
            for item in entries:
                card = self._build_item_card(item)
                self.c_lay.addWidget(card)

        self.c_lay.addStretch(1)
        scroll.setWidget(container)
        self.body.addWidget(scroll, 1)

    def _build_item_card(self, item: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet("background: rgba(255,255,255,0.05); border-radius: 8px; padding: 6px 10px;")
        lay = QHBoxLayout(card)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(10)

        # Left: file info
        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        flow_txt = f"<b>{item.get('src_name')}</b>  ➔  <span style='color: #5ac8ff; font-weight: 700;'>{item.get('out_name')}</span>"
        lbl_flow = QLabel(flow_txt)
        lbl_flow.setStyleSheet("font-size: 9.5pt; color: #ffffff;")

        details = f"{item.get('time_str')} · {human_size(item.get('src_size', 0))} ➔ {human_size(item.get('out_size', 0))}"
        ratio = item.get("ratio", 0.0)
        if ratio > 0:
            details += f"  <span style='color: #8dffb8;'>({ratio}% menor)</span>"
        lbl_det = QLabel(details)
        lbl_det.setObjectName("dim")

        info_col.addWidget(lbl_flow)
        info_col.addWidget(lbl_det)
        lay.addLayout(info_col, 1)

        # Right: action buttons
        out_path = Path(item.get("out_path", ""))
        btn_open = QPushButton("👁️ Abrir")
        btn_open.setStyleSheet("padding: 4px 8px; background: rgba(90, 200, 255, 0.15); border-radius: 6px; color: #5ac8ff; font-weight: 600;")
        btn_open.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(out_path))))
        lay.addWidget(btn_open)

        btn_folder = QPushButton("📁 Pasta")
        btn_folder.setStyleSheet("padding: 4px 8px; background: rgba(255,255,255,0.08); border-radius: 6px; color: #cbd5e1;")
        folder = str(out_path.parent)
        btn_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(folder)))
        lay.addWidget(btn_folder)

        return card

    def _do_clear(self):
        clear_history()
        self.close()

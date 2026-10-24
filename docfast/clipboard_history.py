"""DocFAST Liquid Clipboard History.
Visual translucent clipboard manager storing the last 25 items
(text, code, spreadsheets, URLs, and image thumbnails).
"""
from __future__ import annotations

import base64
import html
import io
import json
import os
import sys
import time
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QGuiApplication, QIcon,
                            QImage, QPainter, QPixmap)
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
                                QLineEdit, QPushButton, QScrollArea,
                                QSizePolicy, QVBoxLayout, QWidget)

from . import glass
from .util import ui_family
from .window import GlassWindow

IS_WIN = sys.platform == "win32"


def hist_file_path() -> Path:
    if IS_WIN:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "DocFAST"
    else:
        base = Path.home() / ".config" / "DocFAST"
    base.mkdir(parents=True, exist_ok=True)
    return base / "clipboard_history.json"


class ClipboardHistoryManager:
    _instance: ClipboardHistoryManager | None = None

    def __init__(self):
        self.items: list[dict] = []
        self._last_text = ""
        self._load()

    @classmethod
    def get_instance(cls) -> ClipboardHistoryManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def attach_listener(self):
        app = QApplication.instance()
        if app:
            cb = app.clipboard()
            cb.dataChanged.connect(self._on_clipboard_changed)

    def _on_clipboard_changed(self):
        app = QApplication.instance()
        if not app:
            return
        cb = app.clipboard()
        mime = cb.mimeData()
        if mime is None:
            return

        now_str = time.strftime("%H:%M:%S")

        # 1. Text or code or table
        if mime.hasText():
            txt = cb.text().strip()
            if not txt or txt == self._last_text:
                return
            self._last_text = txt

            kind = "code" if any(c in txt for c in ("def ", "import ", "SELECT ", "{", "}", ";", "=>")) else \
                   ("table" if ("\t" in txt or "\n" in txt and "," in txt) else "text")

            # Remove existing duplicate
            self.items = [i for i in self.items if i.get("text") != txt]
            self.items.insert(0, {
                "id": str(time.time()),
                "type": kind,
                "text": txt,
                "time": now_str,
                "length": len(txt),
            })
            self._trim_and_save()

        # 2. Image
        elif mime.hasImage():
            img = cb.image()
            if not img.isNull():
                thumb = img.scaled(180, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                buf = io.BytesIO()
                # Save as PNG base64
                pil_im = Image.fromqimage(thumb)
                pil_im.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")

                self.items.insert(0, {
                    "id": str(time.time()),
                    "type": "image",
                    "b64": b64,
                    "w": img.width(),
                    "h": img.height(),
                    "time": now_str,
                })
                self._trim_and_save()

    def _trim_and_save(self):
        self.items = self.items[:25]
        try:
            p = hist_file_path()
            p.write_text(json.dumps(self.items, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load(self):
        p = hist_file_path()
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self.items = data[:25]
            except Exception:
                self.items = []

    def clear(self):
        self.items = []
        try:
            p = hist_file_path()
            if p.exists():
                p.unlink()
        except Exception:
            pass


class ClipboardHistoryWindow(GlassWindow):
    def __init__(self, on_copied=None, parent=None):
        super().__init__("Histórico da Área de Transferência", size=(480, 540))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.on_copied = on_copied
        self.mgr = ClipboardHistoryManager.get_instance()
        self.filter_type = "all"

        # Search bar & Clear
        top_bar = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Buscar no histórico...")
        self.txt_search.textChanged.connect(self._render_items)
        self.txt_search.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                color: #ffffff;
                padding: 6px 10px;
                font-size: 9.5pt;
            }
        """)
        top_bar.addWidget(self.txt_search, 1)

        btn_clear = QPushButton("Limpar")
        btn_clear.setStyleSheet("background: rgba(239, 68, 68, 0.2); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 6px; color: #fecaca; font-size: 8.5pt; padding: 5px 10px;")
        btn_clear.clicked.connect(self._clear_all)
        top_bar.addWidget(btn_clear)
        self.body.addLayout(top_bar)

        # Filter buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.btn_all = QPushButton("Todos")
        self.btn_text = QPushButton("📄 Textos")
        self.btn_img = QPushButton("🖼️ Imagens")
        self.btn_code = QPushButton("📊 Código / Tabelas")

        for b, f_type in [(self.btn_all, "all"), (self.btn_text, "text"),
                          (self.btn_img, "image"), (self.btn_code, "code")]:
            b.setCheckable(True)
            b.setStyleSheet("""
                QPushButton { background: rgba(255,255,255,0.06); border-radius: 6px; padding: 4px 8px; font-size: 8.5pt; color: #e2e8f0; }
                QPushButton:checked { background: rgba(90, 200, 255, 0.25); border: 1px solid #5ac8ff; font-weight: 700; color: #ffffff; }
            """)
            b.clicked.connect(lambda _, t=f_type: self._set_filter(t))
            btn_row.addWidget(b)
        self.btn_all.setChecked(True)
        self.body.addLayout(btn_row)

        # Scroll area for items
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")

        self.list_container = QWidget()
        self.list_container.setStyleSheet("background: transparent;")
        self.item_layout = QVBoxLayout(self.list_container)
        self.item_layout.setContentsMargins(0, 4, 0, 4)
        self.item_layout.setSpacing(6)
        self.scroll.setWidget(self.list_container)

        self.body.addWidget(self.scroll, 1)
        self._render_items()

    def _set_filter(self, f_type: str):
        self.filter_type = f_type
        for b, t in [(self.btn_all, "all"), (self.btn_text, "text"),
                     (self.btn_img, "image"), (self.btn_code, "code")]:
            b.setChecked(t == f_type)
        self._render_items()

    def _clear_all(self):
        self.mgr.clear()
        self._render_items()

    def _render_items(self):
        # Clear existing
        while self.item_layout.count() > 0:
            it = self.item_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        query = self.txt_search.text().lower().strip()
        items = self.mgr.items

        filtered = []
        for it in items:
            t = it.get("type", "text")
            if self.filter_type == "text" and t not in ("text", "table"):
                continue
            if self.filter_type == "image" and t != "image":
                continue
            if self.filter_type == "code" and t not in ("code", "table"):
                continue

            if query:
                if t == "image":
                    continue
                if query not in it.get("text", "").lower():
                    continue
            filtered.append(it)

        if not filtered:
            lbl_empty = QLabel("Nenhum item na área de transferência.")
            lbl_empty.setAlignment(Qt.AlignCenter)
            lbl_empty.setObjectName("dim")
            lbl_empty.setStyleSheet("color: #94a3b8; padding: 40px 0;")
            self.item_layout.addWidget(lbl_empty)
            return

        for it in filtered:
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 8px;
                    padding: 6px;
                }
                QFrame:hover {
                    background: rgba(90, 200, 255, 0.12);
                    border: 1px solid rgba(90, 200, 255, 0.35);
                }
            """)
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(8, 6, 8, 6)
            c_lay.setSpacing(4)

            hdr = QHBoxLayout()
            icon_str = "🖼️ Imagem" if it["type"] == "image" else ("📊 Tabela" if it["type"] == "table" else ("💻 Código" if it["type"] == "code" else "📄 Texto"))
            lbl_type = QLabel(icon_str)
            lbl_type.setStyleSheet("font-weight: 700; font-size: 8.5pt; color: #5ac8ff;")
            lbl_time = QLabel(it.get("time", ""))
            lbl_time.setStyleSheet("font-size: 8pt; color: #94a3b8;")
            hdr.addWidget(lbl_type)
            hdr.addStretch(1)
            hdr.addWidget(lbl_time)
            c_lay.addLayout(hdr)

            if it["type"] == "image":
                lbl_thumb = QLabel()
                try:
                    raw_b64 = it.get("b64", "")
                    raw_bytes = base64.b64decode(raw_b64)
                    pm = QPixmap()
                    pm.loadFromData(raw_bytes)
                    lbl_thumb.setPixmap(pm.scaled(180, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                except Exception:
                    lbl_thumb.setText("[Miniatura indisponível]")
                c_lay.addWidget(lbl_thumb)
                btn_copy = QPushButton("Copiar Imagem")
                btn_copy.clicked.connect(lambda _, item=it: self._copy_image_item(item))
            else:
                raw_txt = it.get("text", "")
                preview = raw_txt[:160].replace("\n", " ") + ("…" if len(raw_txt) > 160 else "")
                lbl_txt = QLabel(preview)
                lbl_txt.setWordWrap(True)
                lbl_txt.setStyleSheet("color: #e2e8f0; font-size: 9pt;")
                c_lay.addWidget(lbl_txt)
                btn_copy = QPushButton("Copiar Texto")
                btn_copy.clicked.connect(lambda _, item=it: self._copy_text_item(item))

            btn_copy.setStyleSheet("background: rgba(255,255,255,0.08); border-radius: 5px; padding: 4px; font-size: 8.5pt; color: #ffffff;")
            c_lay.addWidget(btn_copy)
            self.item_layout.addWidget(card)

        self.item_layout.addStretch(1)

    def _copy_text_item(self, it: dict):
        cb = QApplication.clipboard()
        cb.setText(it.get("text", ""))
        self.close()
        if self.on_copied:
            self.on_copied("Texto copiado para a Área de Transferência!")

    def _copy_image_item(self, it: dict):
        try:
            raw_bytes = base64.b64decode(it.get("b64", ""))
            pm = QPixmap()
            pm.loadFromData(raw_bytes)
            cb = QApplication.clipboard()
            cb.setPixmap(pm)
            self.close()
            if self.on_copied:
                self.on_copied("Imagem copiada para a Área de Transferência!")
        except Exception:
            pass

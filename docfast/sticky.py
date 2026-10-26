"""DocFAST Sticky Notes (Notas Rápidas Fixas de Vidro).
Lightweight, elegant, translucent desktop notes with stay-on-top,
multiple color tints, and persistent storage.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
                                QPushButton, QSizePolicy, QTextEdit,
                                QVBoxLayout, QWidget)

from . import glass
from .util import ui_family
from .window import GlassWindow

IS_WIN = sys.platform == "win32"

NOTE_TINTS = {
    "yellow": ("#fff8db", "rgba(254, 240, 138, 0.18)", "rgba(250, 204, 21, 0.4)"),
    "aurora": ("#e0e7ff", "rgba(99, 102, 241, 0.18)", "rgba(129, 140, 248, 0.4)"),
    "mint":   ("#dcfce7", "rgba(34, 197, 94, 0.16)", "rgba(74, 222, 128, 0.4)"),
    "slate":  ("#f1f5f9", "rgba(148, 163, 184, 0.16)", "rgba(203, 213, 225, 0.3)"),
    "rose":   ("#ffe4e6", "rgba(244, 63, 94, 0.16)", "rgba(251, 113, 133, 0.4)"),
}


def notes_file_path() -> Path:
    if IS_WIN:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "DocFAST"
    else:
        base = Path.home() / ".config" / "DocFAST"
    base.mkdir(parents=True, exist_ok=True)
    return base / "sticky_notes.json"


def load_all_notes() -> list[dict]:
    p = notes_file_path()
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def save_all_notes(notes: list[dict]):
    try:
        p = notes_file_path()
        p.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


class StickyNoteWindow(GlassWindow):
    active_instances: list[StickyNoteWindow] = []

    def __init__(self, note_id: str | None = None, content: str = "", tint: str = "yellow",
                 pos: tuple[int, int] | None = None, parent=None):
        import uuid
        self.note_id = note_id or str(uuid.uuid4())[:8]
        self.tint_key = tint if tint in NOTE_TINTS else "yellow"
        self._pinned = True

        super().__init__("Nota Rápida", size=(280, 240))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        StickyNoteWindow.active_instances.append(self)

        # Note Header Actions
        hdr = QHBoxLayout()
        hdr.setContentsMargins(6, 4, 6, 4)
        hdr.setSpacing(4)

        lbl_icon = QLabel("📝")
        lbl_icon.setStyleSheet("font-size: 11pt;")
        hdr.addWidget(lbl_icon)

        self.lbl_title = QLabel("Nota Fixa")
        self.lbl_title.setStyleSheet("font-weight: 700; font-size: 9pt; color: #ffffff;")
        hdr.addWidget(self.lbl_title)
        hdr.addStretch(1)

        # Pin button
        self.btn_pin = QPushButton("📌")
        self.btn_pin.setFixedSize(24, 24)
        self.btn_pin.setStyleSheet("border: none; background: transparent; font-size: 10pt;")
        self.btn_pin.clicked.connect(self._toggle_pin)
        hdr.addWidget(self.btn_pin)

        # Color cycle button
        self.btn_color = QPushButton("🎨")
        self.btn_color.setFixedSize(24, 24)
        self.btn_color.setStyleSheet("border: none; background: transparent; font-size: 10pt;")
        self.btn_color.clicked.connect(self._cycle_color)
        hdr.addWidget(self.btn_color)

        # New note button
        btn_new = QPushButton("➕")
        btn_new.setFixedSize(24, 24)
        btn_new.setStyleSheet("border: none; background: transparent; font-size: 10pt;")
        btn_new.clicked.connect(lambda: StickyNoteWindow.create_new())
        hdr.addWidget(btn_new)

        # Delete button
        btn_del = QPushButton("🗑️")
        btn_del.setFixedSize(24, 24)
        btn_del.setStyleSheet("border: none; background: transparent; font-size: 9pt;")
        btn_del.clicked.connect(self._delete_note)
        hdr.addWidget(btn_del)

        self.body.addLayout(hdr)

        # Editor Area
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Digite aqui sua anotação ou lista de tarefas...")
        self.editor.setPlainText(content)
        self.editor.textChanged.connect(self._schedule_save)
        self.editor.setStyleSheet("""
            QTextEdit {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                color: #ffffff;
                font-size: 10pt;
                padding: 6px;
                line-height: 1.4;
            }
        """)
        self.body.addWidget(self.editor, 1)

        # Save debounce timer
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._save_to_disk)

        if pos:
            self.move(pos[0], pos[1])
        else:
            # Stagger position
            count = len(StickyNoteWindow.active_instances)
            self.move(100 + (count * 30), 100 + (count * 30))

        self._apply_tint()

    def _toggle_pin(self):
        self._pinned = not self._pinned
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self._pinned)
        self.btn_pin.setText("📌" if self._pinned else "📍")
        self.show()

    def _cycle_color(self):
        keys = list(NOTE_TINTS.keys())
        idx = (keys.index(self.tint_key) + 1) % len(keys)
        self.tint_key = keys[idx]
        self._apply_tint()
        self._save_to_disk()

    def _apply_tint(self):
        _, bg, border = NOTE_TINTS[self.tint_key]
        self.setStyleSheet(f"""
            QFrame#card {{
                background: {bg};
                border: 1.2px solid {border};
            }}
        """)

    def _schedule_save(self):
        self._save_timer.start()

    def _save_to_disk(self):
        all_data = load_all_notes()
        all_data = [n for n in all_data if n.get("id") != self.note_id]
        all_data.append({
            "id": self.note_id,
            "content": self.editor.toPlainText(),
            "tint": self.tint_key,
            "x": self.x(),
            "y": self.y(),
            "w": self.width(),
            "h": self.height(),
        })
        save_all_notes(all_data)

    def _delete_note(self):
        if self in StickyNoteWindow.active_instances:
            StickyNoteWindow.active_instances.remove(self)
        all_data = load_all_notes()
        all_data = [n for n in all_data if n.get("id") != self.note_id]
        save_all_notes(all_data)
        self.close()

    def closeEvent(self, event):
        self._save_to_disk()
        if self in StickyNoteWindow.active_instances:
            StickyNoteWindow.active_instances.remove(self)
        super().closeEvent(event)

    @classmethod
    def create_new(cls, content: str = "") -> StickyNoteWindow:
        note = cls(content=content)
        note.show()
        return note

    @classmethod
    def restore_all(cls):
        """Restore at most 1 note on application startup, avoiding multiple popups."""
        if cls.active_instances:
            return
        data = load_all_notes()
        if not data:
            return
        # Open only the single most recent note
        valid = [item for item in data if item.get("content", "").strip()]
        target = valid[-1] if valid else data[-1]
        pos = (target.get("x", 120), target.get("y", 120))
        w = cls(note_id=target.get("id"), content=target.get("content", ""),
                tint=target.get("tint", "yellow"), pos=pos)
        w.show()

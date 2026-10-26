"""Watch Folders (Pastas Monitoradas) for DocFAST.
Continuously monitors designated directories and automatically converts new incoming files
to the configured target format, with optional safe archiving or recycling.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

from PySide6.QtCore import QObject, QTimer, Signal, Qt
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel,
                                QLineEdit, QComboBox, QPushButton, QScrollArea,
                                QVBoxLayout, QWidget, QCheckBox)

from . import convert
from .safe_trash import move_to_trash
from .util import category
from .window import GlassWindow


def _watch_config_file() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "DocFAST"
    else:
        base = Path.home() / ".config" / "DocFAST"
    base.mkdir(parents=True, exist_ok=True)
    return base / "watch_folders.json"


def load_watch_rules() -> list[dict]:
    p = _watch_config_file()
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return []


def save_watch_rules(rules: list[dict]):
    try:
        _watch_config_file().write_text(json.dumps(rules, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


class WatchFolderManager(QObject):
    """Monitors configured directories periodically."""
    file_converted = Signal(str, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules = load_watch_rules()
        self._seen_files: dict[str, float] = {}  # path -> mtime
        self.timer = QTimer(self)
        self.timer.setInterval(3500)  # check every 3.5s
        self.timer.timeout.connect(self._scan)

    def start(self):
        self.rules = load_watch_rules()
        self._seed_existing()
        self.timer.start()

    def stop(self):
        self.timer.stop()

    def reload(self):
        self.rules = load_watch_rules()
        self._seed_existing()

    def _seed_existing(self):
        """Remembers existing files so we only convert genuinely new arrivals."""
        for r in self.rules:
            if not r.get("enabled", True):
                continue
            folder = Path(r.get("folder", ""))
            if folder.exists() and folder.is_dir():
                for f in folder.glob("*"):
                    if f.is_file():
                        self._seen_files[str(f.resolve())] = f.stat().st_mtime

    def _scan(self):
        for r in self.rules:
            if not r.get("enabled", True):
                continue
            folder = Path(r.get("folder", ""))
            if not folder.exists() or not folder.is_dir():
                continue

            target = r.get("target", "PDF")
            action_after = r.get("action_after", "keep")  # keep, recycle, archive

            for f in folder.glob("*"):
                if not f.is_file():
                    continue
                resolved = str(f.resolve())
                # Ignore temporary or hidden files
                if f.name.startswith((".", "~$", "_")):
                    continue

                mtime = f.stat().st_mtime
                if resolved not in self._seen_files:
                    # New file detected! Wait brief moment to confirm file write is finished
                    self._seen_files[resolved] = mtime
                    self._process_file(f, target, action_after)

    def _process_file(self, file_path: Path, target: str, action_after: str):
        cat = category(file_path)
        if not cat:
            return
        try:
            time.sleep(0.5)  # allow disk flush
            outs = convert.convert(file_path, cat, target)
            if outs:
                self.file_converted.emit(str(file_path), [str(o) for o in outs])
                # Post action
                if action_after == "recycle":
                    move_to_trash(file_path)
                elif action_after == "archive":
                    arch_dir = file_path.parent / "_processados"
                    arch_dir.mkdir(exist_ok=True)
                    dest = arch_dir / file_path.name
                    counter = 1
                    while dest.exists():
                        dest = arch_dir / f"{file_path.stem}_{counter}{file_path.suffix}"
                        counter += 1
                    file_path.rename(dest)
        except Exception:
            pass


class WatchFoldersDialog(GlassWindow):
    """Configuration dialog to add, enable, or remove Watch Folders."""

    def __init__(self, watch_mgr: WatchFolderManager, parent=None):
        super().__init__("📂 Pastas Monitoradas (Automação Contínua)", size=(620, 500))
        self.mgr = watch_mgr
        self.rules = load_watch_rules()

        sub = QLabel("Cadastre pastas locais: todo arquivo que você salvar ou mover para elas será convertido automaticamente.")
        sub.setWordWrap(True)
        sub.setObjectName("dim")
        self.body.addWidget(sub)
        self.body.addSpacing(6)

        # New rule bar
        add_frame = QFrame()
        add_frame.setStyleSheet("background: rgba(255,255,255,0.06); border-radius: 8px; padding: 6px 10px;")
        af_lay = QHBoxLayout(add_frame)
        af_lay.setSpacing(8)

        self.edit_path = QLineEdit()
        self.edit_path.setPlaceholderText("Selecione a pasta para monitorar...")
        self.edit_path.setReadOnly(True)
        af_lay.addWidget(self.edit_path, 1)

        btn_browse = QPushButton("📁 Escolher")
        btn_browse.setStyleSheet("padding: 6px 10px; background: rgba(90, 200, 255, 0.2); border-radius: 6px;")
        btn_browse.clicked.connect(self._browse)
        af_lay.addWidget(btn_browse)

        self.combo_target = QComboBox()
        self.combo_target.addItems(["PDF", "PNG", "JPG", "CSV", "XLSX", "TXT", "JSON"])
        af_lay.addWidget(self.combo_target)

        btn_add = QPushButton("➕ Adicionar")
        btn_add.setObjectName("primary")
        btn_add.clicked.connect(self._add_rule)
        af_lay.addWidget(btn_add)

        self.body.addWidget(add_frame)
        self.body.addSpacing(10)

        # Rules list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        self.list_container = QWidget()
        self.l_lay = QVBoxLayout(self.list_container)
        self.l_lay.setContentsMargins(0, 0, 0, 0)
        self.l_lay.setSpacing(6)

        self._refresh_list()
        scroll.setWidget(self.list_container)
        self.body.addWidget(scroll, 1)

        # Footer
        foot = QHBoxLayout()
        foot.addStretch(1)
        btn_close = QPushButton("Salvar e Fechar")
        btn_close.setObjectName("primary")
        btn_close.clicked.connect(self._save_and_close)
        foot.addWidget(btn_close)
        self.body.addLayout(foot)

    def _browse(self):
        f = QFileDialog.getExistingDirectory(self, "Selecione a pasta para monitoramento automático")
        if f:
            self.edit_path.setText(f)

    def _add_rule(self):
        f = self.edit_path.text().strip()
        if not f:
            return
        target = self.combo_target.currentText()
        self.rules.append({
            "folder": f,
            "target": target,
            "action_after": "keep",
            "enabled": True
        })
        self.edit_path.clear()
        self._refresh_list()

    def _refresh_list(self):
        # Clear items
        while self.l_lay.count():
            item = self.l_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.rules:
            lbl = QLabel("Nenhuma pasta monitorada cadastrada.")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setObjectName("dim")
            self.l_lay.addWidget(lbl)
        else:
            for idx, r in enumerate(self.rules):
                row = QFrame()
                row.setStyleSheet("background: rgba(255,255,255,0.05); border-radius: 8px; padding: 6px 10px;")
                rlay = QHBoxLayout(row)
                rlay.setSpacing(8)

                chk = QCheckBox()
                chk.setChecked(r.get("enabled", True))
                chk.toggled.connect(lambda on, i=idx: self._toggle_rule(i, on))
                rlay.addWidget(chk)

                txt = f"📂 <b>{r.get('folder')}</b>  ➔  <span style='color: #5ac8ff; font-weight: 700;'>{r.get('target')}</span>"
                lbl_r = QLabel(txt)
                lbl_r.setStyleSheet("color: #e2e8f0; font-size: 9pt;")
                rlay.addWidget(lbl_r, 1)

                btn_del = QPushButton("Remover")
                btn_del.setStyleSheet("padding: 3px 8px; background: rgba(239,68,68,0.2); border-radius: 5px; color: #fecaca;")
                btn_del.clicked.connect(lambda _, i=idx: self._del_rule(i))
                rlay.addWidget(btn_del)

                self.l_lay.addWidget(row)

        self.l_lay.addStretch(1)

    def _toggle_rule(self, idx: int, on: bool):
        if 0 <= idx < len(self.rules):
            self.rules[idx]["enabled"] = on

    def _del_rule(self, idx: int):
        if 0 <= idx < len(self.rules):
            self.rules.pop(idx)
            self._refresh_list()

    def _save_and_close(self):
        save_watch_rules(self.rules)
        self.mgr.reload()
        self.close()

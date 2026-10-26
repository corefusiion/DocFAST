"""DocFAST LAN Broadcast & Scheduled Corporate Announcements.
Serverless peer-to-peer announcements (DSS, safety alerts, team reminders)
over UDP broadcast with Liquid-Glass desktop popups near the Windows clock.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QGuiApplication, QIcon,
                            QPainter, QPainterPath, QPen)
from PySide6.QtWidgets import (QApplication, QComboBox, QDateTimeEdit, QDialog,
                                QFrame, QHBoxLayout, QLabel, QLineEdit,
                                QProgressBar, QPushButton, QSizePolicy,
                                QTextEdit, QVBoxLayout, QWidget)

from . import glass
from .util import ui_family
from .window import GlassWindow

IS_WIN = sys.platform == "win32"
LAN_PORT = 47832
MAGIC_TYPE = "docfast_lan_announcement"


def scheduled_file_path() -> Path:
    if IS_WIN:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "DocFAST"
    else:
        base = Path.home() / ".config" / "DocFAST"
    base.mkdir(parents=True, exist_ok=True)
    return base / "scheduled_announcements.json"


def load_scheduled() -> list[dict]:
    p = scheduled_file_path()
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def save_scheduled(items: list[dict]):
    try:
        p = scheduled_file_path()
        p.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def current_sender_identity() -> tuple[str, str]:
    """Returns (username, hostname)."""
    user = os.environ.get("USERNAME") or os.environ.get("USER") or "Colega"
    try:
        host = socket.gethostname()
    except Exception:
        host = "PC-LOCAL"
    return user, host


def broadcast_message(title: str, message: str, icon: str = "🛡️") -> bool:
    """Sends a UDP broadcast packet across the local network."""
    user, host = current_sender_identity()
    packet = {
        "id": str(uuid.uuid4())[:8],
        "type": MAGIC_TYPE,
        "sender_name": user,
        "sender_host": host,
        "title": title.strip() or "Comunicado DocFAST",
        "message": message.strip(),
        "icon": icon,
        "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    raw = json.dumps(packet, ensure_ascii=False).encode("utf-8")

    sent = False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Broadcast to LAN
        try:
            sock.sendto(raw, ("<broadcast>", LAN_PORT))
            sent = True
        except Exception:
            pass
        # Also send to localhost so sender tests/sees it
        try:
            sock.sendto(raw, ("127.0.0.1", LAN_PORT))
            sent = True
        except Exception:
            pass
        sock.close()
    except Exception:
        pass
    return sent


class LanBroadcastListener(QTimer):
    """Background listener that catches incoming UDP announcements and emits a Qt signal."""
    announcement_received = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        self.sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._seen_ids: set[str] = set()

    def start_listening(self):
        if self.running:
            return
        self.running = True
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                try:
                    self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except Exception:
                    pass
            self.sock.bind(("", LAN_PORT))
            self.sock.settimeout(1.5)

            def loop():
                while self.running and self.sock:
                    try:
                        data, addr = self.sock.recvfrom(4096)
                        parsed = json.loads(data.decode("utf-8", "ignore"))
                        if parsed.get("type") == MAGIC_TYPE:
                            msg_id = parsed.get("id")
                            if msg_id and msg_id not in self._seen_ids:
                                self._seen_ids.add(msg_id)
                                self.announcement_received.emit(parsed)
                    except socket.timeout:
                        continue
                    except Exception:
                        pass

            self._thread = threading.Thread(target=loop, daemon=True)
            self._thread.start()
        except Exception:
            pass

    def stop_listening(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None


# ---------------------------------------------------------------- Popup Toast Near Windows Clock
class LanNoticeToast(GlassWindow):
    """Floating Liquid-Glass card anchored above the system tray / Windows clock.
    Remains visible for up to 2 minutes (120s) or until dismissed."""

    def __init__(self, data: dict, parent=None):
        title = data.get("title", "Comunicado da Rede")
        super().__init__(title, size=(380, 200))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint | Qt.SubWindow)

        icon_char = data.get("icon", "🛡️")
        sender = f"{data.get('sender_name', 'Colega')} ({data.get('sender_host', 'Rede')})"
        msg = data.get("message", "")
        time_str = data.get("timestamp", datetime.now().strftime("%H:%M"))

        # Header with cheerful icon
        head = QHBoxLayout()
        head.setSpacing(8)
        lbl_ico = QLabel(icon_char)
        lbl_ico.setStyleSheet("font-size: 18pt;")
        head.addWidget(lbl_ico)

        t_box = QVBoxLayout()
        t_box.setSpacing(1)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 11pt; font-weight: 700; color: #5ac8ff;")
        lbl_from = QLabel(f"De: {sender} · {time_str}")
        lbl_from.setStyleSheet("font-size: 8.5pt; color: #94a3b8;")
        t_box.addWidget(lbl_title)
        t_box.addWidget(lbl_from)
        head.addLayout(t_box, 1)
        self.body.addLayout(head)

        # Message text box
        msg_frame = QFrame()
        msg_frame.setStyleSheet("background: rgba(255,255,255,0.06); border-radius: 8px; padding: 8px;")
        mf_lay = QVBoxLayout(msg_frame)
        lbl_msg = QLabel(msg)
        lbl_msg.setWordWrap(True)
        lbl_msg.setStyleSheet("color: #ffffff; font-size: 9.5pt; line-height: 1.35;")
        mf_lay.addWidget(lbl_msg)
        self.body.addWidget(msg_frame, 1)

        # Remaining time progress bar (120 seconds total)
        self.total_seconds = 120
        self.remaining_seconds = 120
        self.bar = QProgressBar()
        self.bar.setFixedHeight(4)
        self.bar.setTextVisible(False)
        self.bar.setRange(0, self.total_seconds)
        self.bar.setValue(self.total_seconds)
        self.bar.setStyleSheet("""
            QProgressBar { background: rgba(255,255,255,0.1); border-radius: 2px; }
            QProgressBar::chunk { background: #5ac8ff; border-radius: 2px; }
        """)
        self.body.addWidget(self.bar)

        # Footer action button
        foot = QHBoxLayout()
        self.lbl_timer = QLabel("Fecha em 2 min")
        self.lbl_timer.setStyleSheet("color: #94a3b8; font-size: 8pt;")
        foot.addWidget(self.lbl_timer)
        foot.addStretch(1)

        btn_ok = QPushButton("✓ Entendido")
        btn_ok.setObjectName("primary")
        btn_ok.setFixedSize(100, 28)
        btn_ok.clicked.connect(self.close)
        foot.addWidget(btn_ok)
        self.body.addLayout(foot)

        # Position in bottom-right corner (above Windows taskbar)
        screen = QGuiApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            x = avail.right() - self.width() - 20
            y = avail.bottom() - self.height() - 20
            self.move(x, y)

        # 1-second countdown ticker
        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(1000)
        self.tick_timer.timeout.connect(self._countdown)
        self.tick_timer.start()

    def _countdown(self):
        self.remaining_seconds -= 1
        self.bar.setValue(self.remaining_seconds)
        mins = self.remaining_seconds // 60
        secs = self.remaining_seconds % 60
        self.lbl_timer.setText(f"Fecha em {mins:02d}:{secs:02d}")
        if self.remaining_seconds <= 0:
            self.tick_timer.stop()
            self.close()


# ---------------------------------------------------------------- Sender & Schedule Dialog
class LanBroadcastDialog(GlassWindow):
    """Dialog for managers and colleagues to broadcast announcements or schedule them."""

    def __init__(self, parent=None):
        super().__init__("Comunicados em Rede Local (DSS & Equipe)", size=(540, 480))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        subtitle = QLabel("Transmita mensagens instantâneas ou agendadas para todas as máquinas da empresa na mesma rede local:")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #94a3b8; font-size: 9pt; margin-bottom: 4px;")
        self.body.addWidget(subtitle)

        # Template presets
        p_row = QHBoxLayout()
        p_row.addWidget(QLabel("Modelos Rápidos:"))
        self.combo_presets = QComboBox()
        self.combo_presets.addItem("Escolha um modelo...", None)
        self.combo_presets.addItem("🛡️ DSS - Diálogo Semanal de Segurança", ("DSS — Diálogo de Segurança", "Olá! Nosso DSS é amanhã às 08:15, fique atento e compareça se possível :)", "🛡️"))
        self.combo_presets.addItem("⚠️ Manutenção Preventiva no Sistema", ("Aviso de Manutenção", "Atenção equipe: realizaremos manutenção programada no sistema interno às 17h. Salvem seus arquivos com antecedência.", "⚠️"))
        self.combo_presets.addItem("☕ Pausa & Café da Equipe", ("Café da Equipe!", "Pessoal, café da tarde especial na sala de reuniões agora às 15:30. Estão todos convidados! ☕", "☕"))
        self.combo_presets.addItem("🎉 Aniversariante do Dia", ("Parabéns ao Aniversariante!", "Hoje é aniversário do nosso colega! Venham dar os parabéns na copa às 16h!", "🎉"))
        self.combo_presets.currentIndexChanged.connect(self._apply_preset)
        p_row.addWidget(self.combo_presets, 1)
        self.body.addLayout(p_row)

        # Title
        self.body.addWidget(QLabel("Título do Comunicado:"))
        self.txt_title = QLineEdit()
        self.txt_title.setText("DSS — Diálogo Semanal de Segurança")
        self.txt_title.setStyleSheet("background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 6px; color: #fff;")
        self.body.addWidget(self.txt_title)

        # Message body
        self.body.addWidget(QLabel("Mensagem do Comunicado:"))
        self.txt_msg = QTextEdit()
        self.txt_msg.setPlaceholderText("Digite aqui a mensagem que aparecerá na tela de todos os computadores da rede...")
        self.txt_msg.setPlainText("Olá! Nosso DSS é amanhã às 08:15, fique atento e compareça se possível :)")
        self.txt_msg.setFixedHeight(90)
        self.txt_msg.setStyleSheet("background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 6px; color: #fff; font-size: 9.5pt;")
        self.body.addWidget(self.txt_msg)

        # Schedule section
        sched_box = QFrame()
        sched_box.setStyleSheet("background: rgba(255,255,255,0.05); border-radius: 8px; padding: 8px;")
        sb_lay = QVBoxLayout(sched_box)
        sb_lay.setSpacing(6)

        lbl_sc = QLabel("⏰ Agendamento para Disparo Futuro (Opcional):")
        lbl_sc.setStyleSheet("font-weight: 600; color: #e2e8f0; font-size: 9pt;")
        sb_lay.addWidget(lbl_sc)

        s_row = QHBoxLayout()
        self.dt_picker = QDateTimeEdit(datetime.now())
        self.dt_picker.setCalendarPopup(True)
        self.dt_picker.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.dt_picker.setStyleSheet("background: rgba(255,255,255,0.1); border-radius: 6px; padding: 4px 8px; color: #fff;")
        s_row.addWidget(self.dt_picker)

        btn_sched = QPushButton("Salvar Agendamento")
        btn_sched.setStyleSheet("background: rgba(90, 200, 255, 0.2); border: 1px solid #5ac8ff; border-radius: 6px; color: #fff; padding: 4px 10px;")
        btn_sched.clicked.connect(self._schedule_announcement)
        s_row.addWidget(btn_sched)
        sb_lay.addLayout(s_row)
        self.body.addWidget(sched_box)

        # Status feedback
        self.lbl_feedback = QLabel("")
        self.lbl_feedback.setStyleSheet("color: #8dffb8; font-weight: 600; font-size: 8.5pt;")
        self.body.addWidget(self.lbl_feedback)

        self.body.addStretch(1)

        # Footer Actions
        foot = QHBoxLayout()
        btn_close = QPushButton("Fechar")
        btn_close.clicked.connect(self.close)
        foot.addWidget(btn_close)
        foot.addStretch(1)

        btn_send_now = QPushButton("📡 Enviar Agora para Toda a Rede")
        btn_send_now.setObjectName("primary")
        btn_send_now.setFixedHeight(34)
        btn_send_now.clicked.connect(self._send_now)
        foot.addWidget(btn_send_now)
        self.body.addLayout(foot)

    def _apply_preset(self):
        data = self.combo_presets.currentData()
        if data:
            t, m, ico = data
            self.txt_title.setText(t)
            self.txt_msg.setPlainText(m)

    def _send_now(self):
        t = self.txt_title.text().strip()
        m = self.txt_msg.toPlainText().strip()
        if not m:
            self.lbl_feedback.setText("⚠️ Digite uma mensagem antes de enviar.")
            self.lbl_feedback.setStyleSheet("color: #ff6b9d;")
            return
        if broadcast_message(t, m):
            self.lbl_feedback.setText("✓ Comunicado transmitido na rede local com sucesso!")
            self.lbl_feedback.setStyleSheet("color: #8dffb8;")
            QTimer.singleShot(1500, self.close)

    def _schedule_announcement(self):
        t = self.txt_title.text().strip()
        m = self.txt_msg.toPlainText().strip()
        dt_str = self.dt_picker.dateTime().toString("yyyy-MM-dd HH:mm")
        items = load_scheduled()
        items.append({
            "id": str(uuid.uuid4())[:8],
            "title": t,
            "message": m,
            "trigger_dt": dt_str,
            "icon": "🛡️" if "DSS" in t.upper() else "📢"
        })
        save_scheduled(items)
        self.lbl_feedback.setText(f"✓ Agendado com sucesso para {self.dt_picker.dateTime().toString('dd/MM/yyyy às HH:mm')}!")
        self.lbl_feedback.setStyleSheet("color: #8dffb8;")

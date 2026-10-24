"""Liquid-Glass AI Chat Window for DocFAST.
Allows conversing with AI models (Gemini, ChatGPT, Claude, OpenCode) about selected text,
spreadsheets, documents, and screenshots on Windows.
"""
from __future__ import annotations

import html
import io
import json
import os
import sys
import threading
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QCursor, QFont, QGuiApplication,
                            QIcon, QPainter, QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
                                QPushButton, QScrollArea, QSizePolicy,
                                QTextEdit, QVBoxLayout, QWidget)

from . import ai_client, glass
from .util import ui_family
from .window import GlassWindow


def history_file_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "DocFAST"
    else:
        base = Path.home() / ".config" / "DocFAST"
    base.mkdir(parents=True, exist_ok=True)
    return base / "ai_chat_history.json"


class ChatMessageBubble(QFrame):
    def __init__(self, role: str, content: str, img_pixmap: QPixmap | None = None, parent=None):
        super().__init__(parent)
        self.role = role
        self.content = content
        self.img_pixmap = img_pixmap
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        # Sender header
        header = QHBoxLayout()
        header.setSpacing(6)
        lbl_sender = QLabel("Você" if role == "user" else "✨ DocFAST AI")
        lbl_sender.setStyleSheet(
            "font-weight: 700; font-size: 9.5pt; color: #5ac8ff;" if role == "user"
            else "font-weight: 700; font-size: 9.5pt; color: #8dffb8;"
        )
        header.addWidget(lbl_sender)
        header.addStretch(1)
        layout.addLayout(header)

        # Image thumbnail if provided
        if img_pixmap and not img_pixmap.isNull():
            lbl_img = QLabel()
            scaled = img_pixmap.scaled(280, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            lbl_img.setPixmap(scaled)
            lbl_img.setStyleSheet("border-radius: 8px; border: 1px solid rgba(255,255,255,0.2);")
            layout.addWidget(lbl_img)

        # Content text (renders rich text/markdown)
        lbl_text = QLabel()
        lbl_text.setTextFormat(Qt.RichText)
        lbl_text.setWordWrap(True)
        lbl_text.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        lbl_text.setOpenExternalLinks(True)
        lbl_text.setStyleSheet("color: #ffffff; font-size: 10pt; line-height: 1.4;")
        lbl_text.setText(self._format_markdown(content))
        layout.addWidget(lbl_text)

    def _format_markdown(self, raw: str) -> str:
        """Lightweight Markdown to clean HTML converter."""
        escaped = html.escape(raw)
        lines = escaped.splitlines()
        out = []
        in_code = False
        for line in lines:
            if line.strip().startswith("```"):
                if in_code:
                    out.append("</code></pre>")
                    in_code = False
                else:
                    out.append("<pre style='background: rgba(0,0,0,0.45); padding: 8px; border-radius: 6px; font-family: monospace; font-size: 9pt;'><code>")
                    in_code = True
                continue
            if in_code:
                out.append(line)
                continue

            # Headers
            if line.startswith("### "):
                out.append(f"<h3 style='color: #7b8cff; margin: 4px 0;'>{line[4:]}</h3>")
            elif line.startswith("## "):
                out.append(f"<h2 style='color: #5ac8ff; margin: 6px 0;'>{line[3:]}</h2>")
            elif line.startswith("# "):
                out.append(f"<h1 style='color: #5ac8ff; margin: 8px 0;'>{line[2:]}</h1>")
            elif line.startswith("- ") or line.startswith("* "):
                out.append(f"• {line[2:]}<br>")
            else:
                # bold and italic
                import re
                line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
                line = re.sub(r"`(.+?)`", r"<code style='background: rgba(255,255,255,0.12); padding: 2px 4px; border-radius: 4px; font-family: monospace;'>\1</code>", line)
                out.append(f"{line}<br>")

        if in_code:
            out.append("</code></pre>")
        return "".join(out)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = glass.rounded_rect_path(r, 12)
        if self.role == "user":
            p.fillPath(path, QColor(35, 60, 95, 140))
            p.setPen(QPen(QColor(90, 200, 255, 80), 1))
        else:
            p.fillPath(path, glass.current_theme_tint("window"))
            p.setPen(QPen(QColor(255, 255, 255, 45), 1))
        p.drawPath(path)


class AiChatWindow(GlassWindow):
    response_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, settings, initial_text: str = "", initial_image: QPixmap | None = None, parent=None):
        super().__init__("DocFAST Ajuda AI", size=(480, 680), parent=parent)
        self.settings = settings
        self.history: list[dict[str, str]] = []
        self._pending_image_bytes: bytes | None = None
        self._pending_pixmap: QPixmap | None = initial_image
        self._pinned = True

        # Position nicely docked on the right side of screen
        scr = QGuiApplication.primaryScreen().availableGeometry()
        w, h = 480, min(720, scr.height() - 60)
        self.resize(w, h)
        self.move(scr.right() - w - 16, scr.top() + (scr.height() - h) // 2)

        # Keep on top by default so user can view spreadsheets/windows beside it
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        self._build_ui()
        self._load_history()

        self.response_ready.connect(self._on_response_ready)
        self.error_occurred.connect(self._on_error_occurred)

        if initial_image:
            self._set_attached_image(initial_image)

        if initial_text:
            self.input_edit.setPlainText(initial_text)
            if initial_image or len(initial_text) > 15:
                # Auto-send initial question if substantial
                QTimer.singleShot(300, self._send_user_message)

    def _build_ui(self):
        # 1. Header toolbar with Model Pill + Pin + Clear
        tb = QHBoxLayout()
        tb.setSpacing(8)

        model_name = self.settings.get("ai_model") or "gemini-2.5-flash"
        self.lbl_model_badge = QLabel(f"✨ {model_name}")
        self.lbl_model_badge.setStyleSheet(
            "background: rgba(90, 200, 255, 0.22); color: #5ac8ff; "
            "padding: 4px 10px; border-radius: 11px; font-weight: 700; font-size: 8.5pt;"
        )
        tb.addWidget(self.lbl_model_badge)
        tb.addStretch(1)

        self.btn_pin = QPushButton("📌 Fixado")
        self.btn_pin.setToolTip("Fixar esta janela sempre no topo para você navegar em outros programas")
        self.btn_pin.setStyleSheet("font-size: 9pt; padding: 3px 8px; border-radius: 8px;")
        self.btn_pin.clicked.connect(self._toggle_pin)
        tb.addWidget(self.btn_pin)

        btn_clear = QPushButton("🗑️ Limpar")
        btn_clear.setToolTip("Limpar histórico da conversa")
        btn_clear.setStyleSheet("font-size: 9pt; padding: 3px 8px; border-radius: 8px;")
        btn_clear.clicked.connect(self._clear_history)
        tb.addWidget(btn_clear)

        self.body.addLayout(tb)

        # 2. Chat messages scroll area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet("background: transparent; border: none;")

        self.msg_container = QWidget()
        self.msg_container.setStyleSheet("background: transparent;")
        self.msg_layout = QVBoxLayout(self.msg_container)
        self.msg_layout.setContentsMargins(4, 4, 4, 4)
        self.msg_layout.setSpacing(10)
        self.msg_layout.addStretch(1)

        self.scroll.setWidget(self.msg_container)
        self.body.addWidget(self.scroll, 1)

        # 3. Status indicator ("Pensando...")
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #8dffb8; font-size: 9pt; font-weight: 600; padding: 2px 4px;")
        self.lbl_status.hide()
        self.body.addWidget(self.lbl_status)

        # 4. Attachment preview container
        self.attachment_box = QFrame()
        self.attachment_box.setStyleSheet("background: rgba(0,0,0,0.3); border-radius: 8px; padding: 4px;")
        att_layout = QHBoxLayout(self.attachment_box)
        att_layout.setContentsMargins(6, 4, 6, 4)
        self.lbl_att_thumb = QLabel()
        self.lbl_att_text = QLabel("Print de tela anexado")
        self.lbl_att_text.setStyleSheet("color: #a8ffc9; font-size: 9pt; font-weight: 600;")
        btn_del_att = QPushButton("✕")
        btn_del_att.setFixedSize(22, 22)
        btn_del_att.clicked.connect(self._remove_attachment)
        att_layout.addWidget(self.lbl_att_thumb)
        att_layout.addWidget(self.lbl_att_text)
        att_layout.addStretch(1)
        att_layout.addWidget(btn_del_att)
        self.attachment_box.hide()
        self.body.addWidget(self.attachment_box)

        # 5. Input toolbar + multi-line edit
        input_frame = QFrame()
        input_frame.setStyleSheet("background: rgba(255,255,255,0.08); border-radius: 12px; padding: 4px;")
        in_layout = QVBoxLayout(input_frame)
        in_layout.setContentsMargins(8, 8, 8, 8)
        in_layout.setSpacing(6)

        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("Escreva sua dúvida, selecione um texto ou tire um print da tela… [Enter envia]")
        self.input_edit.setStyleSheet(
            "background: transparent; border: none; color: #ffffff; font-size: 10pt; min-height: 52px; max-height: 120px;"
        )
        self.input_edit.installEventFilter(self)
        in_layout.addWidget(self.input_edit)

        bottom_bar = QHBoxLayout()
        btn_snip = QPushButton("📸 Capturar Tela")
        btn_snip.setToolTip("Tirar um print suave da tela para a IA ver e analisar")
        btn_snip.clicked.connect(self._snip_screen)
        bottom_bar.addWidget(btn_snip)
        bottom_bar.addStretch(1)

        self.btn_send = QPushButton("⚡ Enviar")
        self.btn_send.setObjectName("primary")
        self.btn_send.clicked.connect(self._send_user_message)
        bottom_bar.addWidget(self.btn_send)
        in_layout.addLayout(bottom_bar)

        self.body.addWidget(input_frame)

    def eventFilter(self, obj, event):
        if obj == self.input_edit and event.type() == event.Type.KeyPress:
            # Enter sends, Shift+Enter makes newline
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if not (event.modifiers() & Qt.ShiftModifier):
                    self._send_user_message()
                    return True
        return super().eventFilter(obj, event)

    def _toggle_pin(self):
        self._pinned = not self._pinned
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self._pinned)
        self.btn_pin.setText("📌 Fixado" if self._pinned else "📌 Desfixado")
        self.show()

    def _set_attached_image(self, pix: QPixmap):
        self._pending_pixmap = pix
        thumb = pix.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.lbl_att_thumb.setPixmap(thumb)
        buf = io.BytesIO()
        im = Image.fromqpixmap(pix)
        im.save(buf, format="PNG")
        self._pending_image_bytes = buf.getvalue()
        self.attachment_box.show()

    def _remove_attachment(self):
        self._pending_pixmap = None
        self._pending_image_bytes = None
        self.attachment_box.hide()

    def _snip_screen(self):
        """Take a quick screenshot with screen minimization or region selector."""
        self.hide()
        QTimer.singleShot(250, self._do_grab_screen)

    def _do_grab_screen(self):
        screen = QGuiApplication.primaryScreen()
        if screen:
            pix = screen.grabWindow(0)
            self._set_attached_image(pix)
        self.show()
        self.raise_()
        self.activateWindow()

    def _add_bubble(self, role: str, content: str, img_pixmap: QPixmap | None = None):
        bubble = ChatMessageBubble(role, content, img_pixmap)
        idx = self.msg_layout.count() - 1
        self.msg_layout.insertWidget(idx, bubble)
        QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))

    def _send_user_message(self):
        text = self.input_edit.toPlainText().strip()
        img_bytes = self._pending_image_bytes
        img_pix = self._pending_pixmap

        if not text and not img_bytes:
            return

        if not text and img_bytes:
            text = "Analise esta imagem/tela e me explique o que está acontecendo e como resolver."

        # Add to UI and history
        self._add_bubble("user", text, img_pix)
        self.history.append({"role": "user", "content": text})
        self._save_history()

        # Clear inputs
        self.input_edit.clear()
        self._remove_attachment()

        # Start thinking animation
        self.lbl_status.setText("✨ A IA está analisando...")
        self.lbl_status.show()
        self.btn_send.setEnabled(False)

        # Background thread call
        provider = self.settings.get("ai_provider") or "gemini"
        api_key = self.settings.get("ai_api_key") or ""
        model = self.settings.get("ai_model") or ""
        base_url = self.settings.get("ai_base_url") or ""

        def worker():
            try:
                ans = ai_client.send_message(
                    prompt=text,
                    image_bytes=img_bytes,
                    history=self.history[:-1],
                    provider=provider,
                    api_key=api_key,
                    model=model,
                    base_url=base_url,
                )
                self.response_ready.emit(ans)
            except Exception as e:
                self.error_occurred.emit(str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_response_ready(self, response_text: str):
        self.lbl_status.hide()
        self.btn_send.setEnabled(True)
        self._add_bubble("model", response_text)
        self.history.append({"role": "model", "content": response_text})
        self._save_history()

    def _on_error_occurred(self, error_msg: str):
        self.lbl_status.hide()
        self.btn_send.setEnabled(True)
        friendly = f"⚠️ Não foi possível obter resposta:\n\n{error_msg}\n\n*Dica: Verifique sua chave de API e conexão em Configurações → Ajuda AI.*"
        self._add_bubble("model", friendly)

    def _save_history(self):
        try:
            p = history_file_path()
            p.write_text(json.dumps(self.history[-30:], ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load_history(self):
        try:
            p = history_file_path()
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self.history = data
                    for item in self.history[-16:]:
                        self._add_bubble(item.get("role", "user"), item.get("content", ""))
        except Exception:
            self.history = []

    def _clear_history(self):
        self.history = []
        try:
            p = history_file_path()
            if p.exists():
                p.unlink()
        except Exception:
            pass
        # Remove all bubble widgets
        while self.msg_layout.count() > 1:
            item = self.msg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

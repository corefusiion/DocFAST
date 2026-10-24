"""Screen snipper tool + clipboard actions dialogs for DocFAST.
Allows taking region print screens, annotating, saving as PNG/JPG/PDF,
copying to clipboard, and analyzing with DocFAST AI Assistant.
"""
from __future__ import annotations

import io
from pathlib import Path
from PIL import Image

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import (QBrush, QColor, QCursor, QFont, QGuiApplication,
                            QPainter, QPen, QPixmap)
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QHBoxLayout,
                                QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget)

from .util import desktop_dir, unique_path
from .window import GlassWindow


class ScreenSnipper(QWidget):
    """Full-screen dim overlay for selecting a region to screenshot."""

    def __init__(self, on_snip_callback):
        super().__init__(None)
        self.on_snip = on_snip_callback
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)

        # Virtual geometry covers all monitors
        geo = QRect()
        for scr in QGuiApplication.screens():
            geo = geo.united(scr.geometry())
        self.setGeometry(geo)

        # Full capture
        primary = QGuiApplication.primaryScreen()
        self.full_pix = primary.grabWindow(0) if primary else QPixmap()
        self.origin = QPoint()
        self.current = QPoint()
        self.is_selecting = False

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Dim entire desktop
        p.fillRect(self.rect(), QColor(0, 0, 0, 110))

        if self.is_selecting:
            r = QRect(self.origin, self.current).normalized()
            if r.isValid() and r.width() > 1 and r.height() > 1:
                # Clear selected area so desktop shows normally
                p.setCompositionMode(QPainter.CompositionMode_Clear)
                p.fillRect(r, Qt.transparent)
                p.setCompositionMode(QPainter.CompositionMode_SourceOver)

                # Blue border + dimensions
                p.setPen(QPen(QColor("#5ac8ff"), 2))
                p.setBrush(Qt.NoBrush)
                p.drawRect(r)

                dim_txt = f"{r.width()} × {r.height()}"
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(0, 0, 0, 180))
                p.drawRoundedRect(QRect(r.left(), max(0, r.top() - 24), 90, 20), 4, 4)
                p.setPen(QColor("#ffffff"))
                p.setFont(QFont("Segoe UI", 9, QFont.Bold))
                p.drawText(QRect(r.left(), max(0, r.top() - 24), 90, 20), Qt.AlignCenter, dim_txt)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.origin = e.position().toPoint()
            self.current = self.origin
            self.is_selecting = True
            self.update()
        elif e.button() == Qt.RightButton:
            self.close()

    def mouseMoveEvent(self, e):
        if self.is_selecting:
            self.current = e.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.is_selecting:
            self.is_selecting = False
            r = QRect(self.origin, self.current).normalized()
            self.close()
            if r.width() > 5 and r.height() > 5:
                # High-DPI coordinate mapping
                screen = QGuiApplication.screenAt(r.center()) or QGuiApplication.primaryScreen()
                dpr = screen.devicePixelRatio() if screen else 1.0
                mapped = QRect(int(r.x() * dpr), int(r.y() * dpr), int(r.width() * dpr), int(r.height() * dpr))
                snip = self.full_pix.copy(mapped)
                if not snip.isNull():
                    self.on_snip(snip)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Escape, Qt.Key_Q):
            self.close()


class SnipActionDialog(GlassWindow):
    """Floating action dialog shown after screen capture or image paste."""

    def __init__(self, pixmap: QPixmap, app_ref=None):
        super().__init__("Captura de Tela — DocFAST", size=(440, 220))
        self.pix = pixmap
        self.app = app_ref

        layout = self.body
        layout.setSpacing(10)

        # Header with dims
        header = QHBoxLayout()
        lbl_info = QLabel(f"Dimensões: {self.pix.width()} × {self.pix.height()} px")
        lbl_info.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 9pt;")
        header.addWidget(lbl_info)
        header.addStretch(1)
        layout.addLayout(header)

        # Row 1: Direct Save options to Desktop
        row1 = QHBoxLayout()
        btn_png = QPushButton("Salvar PNG (Desktop)")
        btn_png.setObjectName("primary")
        btn_png.clicked.connect(lambda: self._save_file(".png"))

        btn_jpg = QPushButton("Salvar JPG (Desktop)")
        btn_jpg.clicked.connect(lambda: self._save_file(".jpg"))

        btn_pdf = QPushButton("Salvar PDF (Desktop)")
        btn_pdf.clicked.connect(lambda: self._save_file(".pdf"))

        row1.addWidget(btn_png)
        row1.addWidget(btn_jpg)
        row1.addWidget(btn_pdf)
        layout.addLayout(row1)

        # Row 2: Annotate + AI Analysis
        row2 = QHBoxLayout()
        btn_copy = QPushButton("📋 Copiar")
        btn_copy.clicked.connect(self._copy_clipboard)

        btn_annotate = QPushButton("✎ Anotar / Desenhar")
        btn_annotate.clicked.connect(self._annotate)

        btn_ai = QPushButton("✨ Analisar com Ajuda AI")
        btn_ai.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #7b8cff, stop:1 #4f46e5); font-weight: 700;")
        btn_ai.clicked.connect(self._ask_ai)

        row2.addWidget(btn_copy)
        row2.addWidget(btn_annotate)
        row2.addWidget(btn_ai)
        layout.addLayout(row2)

    def _temp_png_path(self) -> Path:
        desk = desktop_dir()
        p = unique_path(desk / "Print_DocFAST.png")
        self.pix.save(str(p), "PNG")
        return p

    def _save_file(self, ext: str):
        filters = {".png": "PNG (*.png)", ".jpg": "JPEG (*.jpg)", ".pdf": "PDF (*.pdf)"}
        desk = desktop_dir()
        default_file = str(unique_path(desk / f"Print{ext}"))
        dest, _ = QFileDialog.getSaveFileName(None, "Salvar Print", default_file, filters.get(ext, "Todos (*.*)"))
        if not dest:
            return

        self.close()
        p = Path(dest)
        if ext == ".pdf":
            im = Image.fromqpixmap(self.pix).convert("RGB")
            im.save(p, "PDF", resolution=150.0)
        else:
            self.pix.save(str(p))

        if self.app:
            self.app.toasts.info("Print Salvo na Área de Trabalho", f"Salvo em: {p.name}")

    def _copy_clipboard(self):
        QApplication.clipboard().setPixmap(self.pix)
        if self.app:
            self.app.toasts.info("Copiado!", "A imagem foi copiada para a Área de Transferência.")
        self.close()

    def _annotate(self):
        self.close()
        tmp_png = self._temp_png_path()
        if self.app:
            from . import tools
            self.app.open_window(tools.AnnotateWindow(str(tmp_png), self.app.notify))

    def _ask_ai(self):
        self.close()
        if self.app:
            self.app.open_ai_chat(initial_text="Analise esta captura de tela e me explique o que está acontecendo.", initial_image=self.pix)


class ClipboardTextDialog(GlassWindow):
    """Floating action dialog shown when text is pasted from clipboard."""

    def __init__(self, text: str, app_ref=None):
        super().__init__("Texto da Área de Transferência — DocFAST", size=(480, 280))
        self.text = text
        self.app = app_ref

        layout = self.body
        layout.setSpacing(10)

        # Preview of copied text
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setPlainText(self.text)
        preview.setStyleSheet("background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.15); border-radius: 8px; color: #e2e8f0; font-size: 9.5pt;")
        layout.addWidget(preview, 1)

        # Row 1: Direct Save to Desktop
        row1 = QHBoxLayout()
        btn_txt = QPushButton("Salvar TXT (Desktop)")
        btn_txt.setObjectName("primary")
        btn_txt.clicked.connect(lambda: self._save_text(".txt"))

        btn_docx = QPushButton("Salvar DOCX (Desktop)")
        btn_docx.clicked.connect(lambda: self._save_text(".docx"))

        btn_pdf = QPushButton("Salvar PDF (Desktop)")
        btn_pdf.clicked.connect(lambda: self._save_text(".pdf"))

        row1.addWidget(btn_txt)
        row1.addWidget(btn_docx)
        row1.addWidget(btn_pdf)
        layout.addLayout(row1)

        # Row 2: AI Assistant
        row2 = QHBoxLayout()
        btn_ai = QPushButton("✨ Conversar sobre este texto com Ajuda AI")
        btn_ai.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #7b8cff, stop:1 #4f46e5); font-weight: 700;")
        btn_ai.clicked.connect(self._ask_ai)
        row2.addWidget(btn_ai)
        layout.addLayout(row2)

    def _save_text(self, ext: str):
        desk = desktop_dir()
        filters = {".txt": "Texto (*.txt)", ".docx": "Documento Word (*.docx)", ".pdf": "PDF (*.pdf)"}
        default_file = str(unique_path(desk / f"Texto_Colado{ext}"))
        dest, _ = QFileDialog.getSaveFileName(None, "Salvar Texto", default_file, filters.get(ext, "Todos (*.*)"))
        if not dest:
            return

        self.close()
        p = Path(dest)
        if ext == ".txt":
            p.write_text(self.text, encoding="utf-8")
        elif ext == ".docx":
            from docx import Document
            doc = Document()
            for line in self.text.splitlines():
                doc.add_paragraph(line)
            doc.save(p)
        elif ext == ".pdf":
            from . import convert
            tmp_txt = desk / "temp_colado.txt"
            tmp_txt.write_text(self.text, encoding="utf-8")
            convert.text_to_pdf(tmp_txt)
            gen_pdf = tmp_txt.with_suffix(".pdf")
            if gen_pdf.exists():
                if gen_pdf != p:
                    if p.exists():
                        p.unlink()
                    gen_pdf.rename(p)
            if tmp_txt.exists():
                tmp_txt.unlink()

        if self.app:
            self.app.toasts.info("Salvo na Área de Trabalho", f"Salvo em: {p.name}")

    def _ask_ai(self):
        self.close()
        if self.app:
            self.app.open_ai_chat(initial_text=f"Dúvida sobre o seguinte texto:\n\n{self.text}")


def handle_clipboard_paste(app):
    """Check clipboard and open appropriate DocFAST actions on Desktop."""
    cb = QApplication.clipboard()
    pix = cb.pixmap()
    if not pix.isNull():
        dlg = SnipActionDialog(pix, app)
        app.open_window(dlg)
        return True

    text = cb.text()
    if text and text.strip():
        dlg = ClipboardTextDialog(text.strip(), app)
        app.open_window(dlg)
        return True

    app.toasts.info("Área de Transferência Vazia", "Nenhuma imagem ou texto encontrado na Área de Transferência.")
    return False


class ScreenGifRecorder(QWidget):
    """Region selector and lightweight animated GIF screen recorder (up to 15s)."""

    def __init__(self, on_gif_saved=None, parent=None):
        super().__init__(None)
        self.on_gif_saved = on_gif_saved
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)

        geo = QRect()
        for scr in QGuiApplication.screens():
            geo = geo.united(scr.geometry())
        self.setGeometry(geo)

        primary = QGuiApplication.primaryScreen()
        self.full_pix = primary.grabWindow(0) if primary else QPixmap()
        self.origin = QPoint()
        self.current = QPoint()
        self.is_selecting = False
        self.selected_rect: QRect | None = None

        self.frames: list[Image.Image] = []
        self.is_recording = False
        self.seconds_elapsed = 0

        # Frame capture timer (10 FPS = 100ms)
        self.frame_timer = QTimer(self)
        self.frame_timer.setInterval(100)
        self.frame_timer.timeout.connect(self._capture_frame)

        # Seconds ticker
        self.sec_timer = QTimer(self)
        self.sec_timer.setInterval(1000)
        self.sec_timer.timeout.connect(self._tick_second)

        # Floating control bar
        self.bar = QFrame(None)
        self.bar.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.bar.setStyleSheet("""
            QFrame {
                background: rgba(15, 23, 42, 0.92);
                border: 1px solid rgba(90, 200, 255, 0.4);
                border-radius: 10px;
                padding: 6px 10px;
            }
        """)
        b_lay = QHBoxLayout(self.bar)
        b_lay.setContentsMargins(6, 4, 6, 4)
        b_lay.setSpacing(8)

        self.btn_rec = QPushButton("🔴 Iniciar Gravação GIF")
        self.btn_rec.setStyleSheet("background: #ef4444; color: #fff; font-weight: 700; border-radius: 6px; padding: 6px 12px;")
        self.btn_rec.clicked.connect(self._toggle_record)
        b_lay.addWidget(self.btn_rec)

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setStyleSheet("background: rgba(255,255,255,0.1); color: #cbd5e1; border-radius: 6px; padding: 6px 10px;")
        self.btn_cancel.clicked.connect(self._cancel)
        b_lay.addWidget(self.btn_cancel)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(0, 0, 0, 110))

        if self.is_selecting or self.selected_rect:
            r = self.selected_rect or QRect(self.origin, self.current).normalized()
            if r.isValid() and r.width() > 1 and r.height() > 1:
                p.setCompositionMode(QPainter.CompositionMode_Clear)
                p.fillRect(r, Qt.transparent)
                p.setCompositionMode(QPainter.CompositionMode_SourceOver)

                # Red border if recording, blue if selecting
                border_color = QColor("#ef4444") if self.is_recording else QColor("#5ac8ff")
                p.setPen(QPen(border_color, 2))
                p.drawRect(r)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.is_recording:
            self.origin = event.pos()
            self.current = event.pos()
            self.is_selecting = True
            self.selected_rect = None
            self.bar.hide()
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.current = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_selecting:
            self.is_selecting = False
            r = QRect(self.origin, self.current).normalized()
            if r.width() > 30 and r.height() > 30:
                self.selected_rect = r
                # Position floating bar just below or above selected area
                bx = max(10, r.center().x() - 140)
                by = r.bottom() + 10 if r.bottom() + 60 < self.height() else r.top() - 50
                self.bar.move(bx, by)
                self.bar.show()
                self.update()
            else:
                self.close()

    def _toggle_record(self):
        if not self.is_recording:
            # Start
            self.is_recording = True
            self.frames = []
            self.seconds_elapsed = 0
            self.btn_rec.setText("⏹ Concluir GIF (00:00 / 00:15)")
            self.btn_rec.setStyleSheet("background: #22c55e; color: #fff; font-weight: 700; border-radius: 6px; padding: 6px 12px;")
            self.btn_cancel.hide()
            self.frame_timer.start()
            self.sec_timer.start()
            self.update()
        else:
            # Stop & save
            self._finish_and_save()

    def _tick_second(self):
        self.seconds_elapsed += 1
        self.btn_rec.setText(f"⏹ Concluir GIF ({self.seconds_elapsed:02d}:00 / 00:15)")
        if self.seconds_elapsed >= 15:
            self._finish_and_save()

    def _capture_frame(self):
        if not self.selected_rect:
            return
        primary = QGuiApplication.primaryScreen()
        if primary:
            pix = primary.grabWindow(0, self.selected_rect.x(), self.selected_rect.y(),
                                     self.selected_rect.width(), self.selected_rect.height())
            im = Image.fromqpixmap(pix)
            self.frames.append(im.convert("P", palette=Image.ADAPTIVE))

    def _finish_and_save(self):
        self.frame_timer.stop()
        self.sec_timer.stop()
        self.bar.hide()
        self.close()

        if self.frames:
            out_file = unique_path(desktop_dir() / "DocFAST_Gravacao.gif")
            first = self.frames[0]
            first.save(
                out_file,
                save_all=True,
                append_images=self.frames[1:],
                duration=100,
                loop=0,
                optimize=True,
            )
            if self.on_gif_saved:
                self.on_gif_saved(out_file)

    def _cancel(self):
        self.frame_timer.stop()
        self.sec_timer.stop()
        self.bar.hide()
        self.close()

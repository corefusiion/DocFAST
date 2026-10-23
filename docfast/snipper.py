"""DocFAST Screen Snipping Tool & Clipboard Integration:
Allows user to capture any screen region (Print) and convert to PNG, JPG, PDF or Annotate,
or convert clipboard image/text immediately with DocFAST.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from PIL import Image

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QCursor, QFont, QGuiApplication,
                            QImage, QPainter, QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout, QWidget)

from . import glass, imaging
from .util import human_size, unique_path


class ScreenSnipper(QWidget):
    """Fullscreen screen snipper with dimmed background and rectangular selection."""
    def __init__(self, on_snip_callback=None):
        super().__init__()
        self.on_snip = on_snip_callback
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setCursor(Qt.CrossCursor)
        
        # Calculate virtual desktop geometry across all connected screens
        screens = QGuiApplication.screens()
        total_rect = QRect()
        for s in screens:
            total_rect = total_rect.united(s.geometry())
        self.geom = total_rect if not total_rect.isEmpty() else QGuiApplication.primaryScreen().geometry()
        self.setGeometry(self.geom)
        
        # Capture the entire desktop
        screen = QGuiApplication.primaryScreen()
        self.screenshot = screen.grabWindow(0)
        
        self.start_pt: QPoint | None = None
        self.curr_pt: QPoint | None = None
        self.snip_rect = QRect()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.start_pt = e.position().toPoint()
            self.curr_pt = self.start_pt
            self.update()
        elif e.button() == Qt.RightButton:
            self.close()

    def mouseMoveEvent(self, e):
        if self.start_pt is not None:
            self.curr_pt = e.position().toPoint()
            self.snip_rect = QRect(self.start_pt, self.curr_pt).normalized()
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.start_pt is not None:
            rect = self.snip_rect
            self.close()
            if rect.width() > 10 and rect.height() > 10:
                # Handle DPI scaling properly
                scale_x = self.screenshot.width() / max(1, self.width())
                scale_y = self.screenshot.height() / max(1, self.height())
                crop_rect = QRect(
                    int(rect.x() * scale_x),
                    int(rect.y() * scale_y),
                    int(rect.width() * scale_x),
                    int(rect.height() * scale_y)
                )
                cropped = self.screenshot.copy(crop_rect)
                if self.on_snip:
                    self.on_snip(cropped)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        # 1. Draw raw screenshot scaled to window bounds
        p.drawPixmap(self.rect(), self.screenshot)
        
        # 2. Dim entire screen except selection
        path_all = QPainterPath()
        path_all.addRect(QRectF(self.rect()))
        
        if not self.snip_rect.isEmpty():
            path_sel = QPainterPath()
            path_sel.addRect(QRectF(self.snip_rect))
            dim_path = path_all.subtracted(path_sel)
            p.fillPath(dim_path, QColor(0, 0, 0, 140))
            
            # Selection border
            p.setPen(QPen(QColor("#2563eb"), 2))
            p.drawRect(self.snip_rect)
            
            # Dimension badge
            txt = f"{self.snip_rect.width()} × {self.snip_rect.height()} px"
            p.setFont(QFont("Segoe UI", 10, QFont.Bold))
            badge_rect = QRect(self.snip_rect.left(), max(10, self.snip_rect.top() - 26), 130, 24)
            p.fillRect(badge_rect, QColor(15, 23, 42, 220))
            p.setPen(QColor(255, 255, 255))
            p.drawText(badge_rect, Qt.AlignCenter, txt)
        else:
            p.fillPath(path_all, QColor(0, 0, 0, 120))
            # Hint text
            p.setFont(QFont("Segoe UI", 14, QFont.Bold))
            p.setPen(QColor(255, 255, 255))
            p.drawText(self.rect(), Qt.AlignCenter, "Arraste com o mouse para selecionar a área do Print\n(Pressione Esc ou clique com o botão direito para cancelar)")


class SnipActionDialog(QDialog):
    """Action popup shown right after taking a screen snip."""
    def __init__(self, pixmap: QPixmap, app_ref=None, parent=None):
        super().__init__(parent)
        self.pix = pixmap
        self.app = app_ref
        self.setWindowTitle("Print Capturado — DocFAST")
        self.setFixedSize(490, 250)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("""
            QDialog { background: #1e1e2e; border: 2px solid rgba(59, 130, 246, 0.6); border-radius: 14px; }
            QLabel { color: #f8fafc; font-family: 'Segoe UI', sans-serif; }
            QPushButton { background: #334155; color: white; border: 1px solid rgba(255,255,255,0.15); border-radius: 8px; padding: 8px 14px; font-weight: 600; font-size: 13px; font-family: 'Segoe UI', sans-serif; }
            QPushButton:hover { background: #475569; border-color: rgba(255,255,255,0.35); }
            QPushButton#primary { background: #2563eb; border: 1px solid #3b82f6; }
            QPushButton#primary:hover { background: #1d4ed8; }
            QPushButton#chrome { background: transparent; border: none; font-size: 14px; color: #94a3b8; }
            QPushButton#chrome:hover { color: #f87171; background: rgba(255,255,255,0.08); }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        
        header = QHBoxLayout()
        title = QLabel(f"<b>Print Capturado:</b> {self.pix.width()} × {self.pix.height()} px")
        title.setStyleSheet("font-size: 15px; color: #60a5fa;")
        header.addWidget(title)
        header.addStretch(1)
        
        btn_x = QPushButton("✕")
        btn_x.setObjectName("chrome")
        btn_x.setFixedSize(28, 28)
        btn_x.clicked.connect(self.close)
        header.addWidget(btn_x)
        layout.addLayout(header)
        
        row1 = QHBoxLayout()
        btn_png = QPushButton("Salvar PNG")
        btn_png.setObjectName("primary")
        btn_png.clicked.connect(lambda: self._save_file(".png"))
        btn_jpg = QPushButton("Salvar JPG")
        btn_jpg.clicked.connect(lambda: self._save_file(".jpg"))
        btn_pdf = QPushButton("Salvar PDF")
        btn_pdf.clicked.connect(lambda: self._save_file(".pdf"))
        row1.addWidget(btn_png)
        row1.addWidget(btn_jpg)
        row1.addWidget(btn_pdf)
        layout.addLayout(row1)
        
        row2 = QHBoxLayout()
        btn_copy = QPushButton("📋 Copiar para Área de Transferência")
        btn_copy.clicked.connect(self._copy_clipboard)
        btn_annotate = QPushButton("✎ Anotar / Desenhar")
        btn_annotate.clicked.connect(self._annotate)
        row2.addWidget(btn_copy)
        row2.addWidget(btn_annotate)
        layout.addLayout(row2)

    def _temp_png_path(self) -> Path:
        d = Path(tempfile.gettempdir()) / "DocFAST"
        d.mkdir(parents=True, exist_ok=True)
        p = d / "docfast_snip.png"
        self.pix.save(str(p), "PNG")
        return p

    def _save_file(self, ext: str):
        filters = {".png": "PNG (*.png)", ".jpg": "JPEG (*.jpg)", ".pdf": "PDF (*.pdf)"}
        dest, _ = QFileDialog.getSaveFileName(None, "Salvar Print", f"Print{ext}", filters.get(ext, "Todos (*.*)"))
        if not dest:
            return
            
        self.close()
        p = Path(dest)
        if ext == ".pdf":
            tmp_png = self._temp_png_path()
            im = Image.open(tmp_png).convert("RGB")
            im.save(p, "PDF", resolution=150.0)
        else:
            self.pix.save(str(p))
            
        if self.app:
            self.app.toasts.info("Print Salvo com Sucesso", f"Salvo em: {p.name}")

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


def handle_clipboard_paste(app):
    """Check clipboard and open DocFAST menu directly on it."""
    cb = QApplication.clipboard()
    pix = cb.pixmap()
    if not pix.isNull():
        d = Path(tempfile.gettempdir()) / "DocFAST"
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "clipboard_image.png"
        pix.save(str(tmp), "PNG")
        app.show_click_menu([str(tmp)])
        return True
        
    text = cb.text()
    if text and text.strip():
        d = Path(tempfile.gettempdir()) / "DocFAST"
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "clipboard_text.txt"
        tmp.write_text(text, encoding="utf-8")
        app.show_click_menu([str(tmp)])
        return True
        
    app.toasts.info("Área de Transferência Vazia", "Nenhuma imagem ou texto encontrado na Área de Transferência.")
    return False

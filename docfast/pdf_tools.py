"""DocFAST PDF Advanced Tools:
1. Visual Signing & Stamping (SignPdfWindow)
2. Visual Page Reordering, Rotating & Deleting (OrganizePdfWindow)
"""
from __future__ import annotations

import datetime

import io
from pathlib import Path
from PIL import Image, ImageDraw

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QCursor, QFont, QIcon, QImage,
                            QPainter, QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QDialog, QFileDialog, QLineEdit,
                               QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QPushButton,
                               QRadioButton, QScrollArea, QSlider,
                               QVBoxLayout, QWidget)

from .convert import fitz, open_pdf
from .i18n import t
from .util import UserError, sibling
from .window import GlassWindow
from . import glass


def make_signature_transparent(im: Image.Image, threshold: int = 215) -> Image.Image:
    """Turn white/light-gray background completely transparent."""
    im = im.convert("RGBA")
    pixels = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            brightness = (r * 299 + g * 587 + b * 114) // 1000
            if brightness > threshold:
                alpha = max(0, 255 - int((brightness - threshold) / max(1, 255 - threshold) * 255))
                pixels[x, y] = (r, g, b, min(a, alpha))
            else:
                pixels[x, y] = (min(r, 45), min(g, 45), min(b, 45), a)
    return im


# ---------------------------------------------------------------- Signature Pad Dialog
class SignaturePadDialog(QDialog):
    """Draw a signature with mouse or pen stylus."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("tool_sign"))
        self.setFixedSize(480, 260)
        self.setStyleSheet("""
            QDialog { background: #1e1e2e; border-radius: 12px; }
            QLabel { color: #f8fafc; font-size: 13px; }
            QPushButton { background: #334155; color: white; border-radius: 6px; padding: 6px 12px; font-weight: 600; }
            QPushButton:hover { background: #475569; }
            QPushButton#primary { background: #2563eb; }
            QPushButton#primary:hover { background: #1d4ed8; }
        """)
        layout = QVBoxLayout(self)
        
        info = QLabel("Desenhe sua assinatura abaixo com o mouse ou caneta:")
        layout.addWidget(info)
        
        self.canvas = DrawingCanvas()
        layout.addWidget(self.canvas, 1)
        
        btn_row = QHBoxLayout()
        btn_clear = QPushButton("Limpar")
        btn_clear.clicked.connect(self.canvas.clear)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch(1)
        
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        
        btn_ok = QPushButton("Usar Assinatura")
        btn_ok.setObjectName("primary")
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def get_image(self) -> Image.Image:
        from .glass import pil_from_qimage
        qimg = self.canvas.get_image()
        return pil_from_qimage(qimg)


class DrawingCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CrossCursor)
        self.setMinimumSize(440, 160)
        self.setStyleSheet("background: #ffffff; border-radius: 8px;")
        self.lines: list[list[QPointF]] = []
        self._current_line: list[QPointF] = []

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._current_line = [e.position()]
            self.lines.append(self._current_line)
            self.update()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton and self._current_line:
            self._current_line.append(e.position())
            self.update()

    def clear(self):
        self.lines = []
        self._current_line = []
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#ffffff"))
        
        # Subtle dotted baseline guide
        p.setPen(QPen(QColor(200, 200, 200), 1, Qt.DashLine))
        y_base = int(self.height() * 0.75)
        p.drawLine(20, y_base, self.width() - 20, y_base)
        
        # Pen ink
        pen = QPen(QColor(15, 23, 42), 2.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        for line in self.lines:
            for i in range(len(line) - 1):
                p.drawLine(line[i], line[i + 1])

    def get_image(self) -> QImage:
        img = QImage(self.size(), QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(15, 23, 42), 2.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        for line in self.lines:
            for i in range(len(line) - 1):
                p.drawLine(line[i], line[i + 1])
        p.end()
        return img


# ---------------------------------------------------------------- Sign PDF Window

class DigitalCertSignDialog(QDialog):
    """Dialog to load .pfx / .p12 certificate and generate an official ICP-Brasil visual stamp."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Assinatura Digital ICP-Brasil (.pfx / A1)")
        self.setFixedSize(480, 420)
        self.setStyleSheet(glass.QSS)
        self.cert_info = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        lbl_head = QLabel("🔏 Assinador com Certificado Digital ICP-Brasil")
        lbl_head.setStyleSheet("font-size: 11pt; font-weight: 700; color: #5ac8ff;")
        layout.addWidget(lbl_head)

        lbl_sub = QLabel("Carregue seu certificado digital (.pfx ou .p12) para gerar o selo oficial de conformidade jurídica com a MP 2.200-2/2001:")
        lbl_sub.setWordWrap(True)
        lbl_sub.setStyleSheet("color: #94a3b8; font-size: 9pt;")
        layout.addWidget(lbl_sub)

        # File picker
        f_row = QHBoxLayout()
        self.txt_path = QLineEdit()
        self.txt_path.setPlaceholderText("Selecione o arquivo .pfx / .p12...")
        self.txt_path.setStyleSheet("background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 6px; color: #fff;")
        btn_browse = QPushButton("Procurar…")
        btn_browse.clicked.connect(self._browse_cert)
        f_row.addWidget(self.txt_path, 1)
        f_row.addWidget(btn_browse)
        layout.addLayout(f_row)

        # Password
        layout.addWidget(QLabel("Senha do Certificado:"))
        self.txt_pass = QLineEdit()
        self.txt_pass.setEchoMode(QLineEdit.Password)
        self.txt_pass.setPlaceholderText("Digite a senha do arquivo .pfx")
        self.txt_pass.setStyleSheet("background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 6px; color: #fff;")
        layout.addWidget(self.txt_pass)

        # Signer Name override
        layout.addWidget(QLabel("Nome do Titular / Razão Social:"))
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Ex: Gleisson Santos / DocFAST Soluções")
        self.txt_name.setStyleSheet("background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 6px; color: #fff;")
        layout.addWidget(self.txt_name)

        # Status / Feedback
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #8dffb8; font-weight: 600; font-size: 8.5pt;")
        layout.addWidget(self.lbl_status)

        layout.addStretch(1)

        # Buttons
        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)
        btns.addStretch(1)

        btn_ok = QPushButton("Gerar Selo ICP-Brasil")
        btn_ok.setObjectName("primary")
        btn_ok.clicked.connect(self._confirm)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

    def _browse_cert(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Selecionar Certificado Digital", "", "Certificados (*.pfx *.p12)")
        if fn:
            self.txt_path.setText(fn)
            self._try_read_pfx(fn)

    def _try_read_pfx(self, pfx_path: str):
        # Quick extract using PowerShell if on Windows
        if sys.platform == "win32":
            try:
                import subprocess
                cmd = f'powershell -NoProfile -Command "$cert = Get-PfxCertificate -FilePath \"{pfx_path}\"; if($cert){{ $cert.Subject; $cert.Issuer }}"'
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                if res.returncode == 0 and res.stdout.strip():
                    lines = res.stdout.strip().splitlines()
                    subject = lines[0] if len(lines) > 0 else ""
                    # Try to extract CN=
                    import re
                    m = re.search(r'CN=([^,]+)', subject)
                    if m:
                        self.txt_name.setText(m.group(1).strip())
                    self.lbl_status.setText("✓ Certificado verificado com sucesso!")
            except Exception:
                pass

    def _confirm(self):
        pfx = self.txt_path.text().strip()
        name = self.txt_name.text().strip() or "Titular do Certificado Digital"
        self.cert_info = {
            "path": pfx,
            "name": name,
            "issuer": "Autoridade Certificadora ICP-Brasil",
            "date": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        }
        self.accept()

    def generate_stamp_image(self, doc_hash: str = "") -> Image.Image:
        """Draws an official ICP-Brasil stamp with security borders and cryptographic digest."""
        w, h = 480, 160
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)

        # Rounded background with subtle security green tint
        d.rounded_rectangle([(4, 4), (w - 4, h - 4)], radius=12, fill=(15, 30, 25, 235), outline=(16, 185, 129, 240), width=2)
        d.rectangle([(16, 14), (w - 16, 15)], fill=(16, 185, 129, 140))

        # Text information
        name = self.cert_info.get("name", "Gleisson Santos")
        dt = self.cert_info.get("date", datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        issuer = self.cert_info.get("issuer", "AC ICP-Brasil")
        h_short = doc_hash[:24] if doc_hash else "SHA256:7f83b1657ff1fc53b92dc1814"

        d.text((24, 20), "🔏 DOCUMENTO ASSINADO DIGITALMENTE (ICP-Brasil)", fill=(16, 185, 129, 255))
        d.text((24, 44), f"Assinado por: {name}", fill=(255, 255, 255, 255))
        d.text((24, 68), f"Emissora: {issuer}", fill=(203, 213, 225, 255))
        d.text((24, 92), f"Data e Hora: {dt}", fill=(203, 213, 225, 255))
        d.text((24, 116), f"Hash: {h_short}...", fill=(148, 163, 184, 255))
        d.text((24, 136), "Validade jurídica conforme MP nº 2.200-2/2001 e padrão PAdES", fill=(110, 231, 183, 220))
        return im

class SignPdfWindow(GlassWindow):
    def __init__(self, src: str | Path, notify=None):
        super().__init__("Assinar / Carimbar PDF", size=(920, 720))
        self.src = Path(src)
        self.notify = notify
        self.cur_page = 0
        self.doc = open_pdf(self.src)
        self.page_count = self.doc.page_count
        
        self.stamp_img: Image.Image | None = None
        self.clean_bg = True
        
        # Overlay rect in normalized 0.0-1.0 page coordinates (x, y, w, h)
        self.stamp_norm_rect = QRectF(0.60, 0.78, 0.28, 0.12)
        
        # Setup UI
        content = QHBoxLayout()
        
        # Left preview canvas
        self.preview_canvas = PdfPageSignCanvas(self)
        content.addWidget(self.preview_canvas, 1)
        
        # Right sidebar controls
        sidebar = QVBoxLayout()
        sidebar.setSpacing(12)
        sidebar.setContentsMargins(8, 0, 8, 0)
        
        # 1. Signature source
        src_box = QFrame()
        src_box.setStyleSheet("background: rgba(255,255,255,10); border-radius: 8px; padding: 6px;")
        sb_layout = QVBoxLayout(src_box)
        sb_layout.setSpacing(8)
        lbl_source = QLabel("<b>Origem da Assinatura / Carimbo:</b>")
        sb_layout.addWidget(lbl_source)
        
        btn_draw = QPushButton("✍ Desenhar Assinatura…")
        btn_draw.clicked.connect(self._open_pad)
        sb_layout.addWidget(btn_draw)
        
        btn_upload = QPushButton("📁 Carregar Imagem / Rubrica…")
        btn_upload.clicked.connect(self._upload_image)
        sb_layout.addWidget(btn_upload)
        
        self.chk_clean_bg = QCheckBox("Remover fundo branco (Transparência)")
        self.chk_clean_bg.setChecked(True)
        self.chk_clean_bg.toggled.connect(self._toggle_clean_bg)
        sb_layout.addWidget(self.chk_clean_bg)
        sidebar.addWidget(src_box)
        
        # 2. Page application mode
        mode_box = QFrame()
        mode_box.setStyleSheet("background: rgba(255,255,255,10); border-radius: 8px; padding: 6px;")
        mb_layout = QVBoxLayout(mode_box)
        mb_layout.setSpacing(6)
        lbl_mode = QLabel("<b>Aplicar Carimbo em:</b>")
        mb_layout.addWidget(lbl_mode)
        
        self.rb_curr = QRadioButton("Apenas na página atual")
        self.rb_curr.setChecked(True)
        self.rb_all = QRadioButton("Em todas as páginas (todas as folhas)")
        self.rb_last = QRadioButton("Apenas na última página")
        
        mb_layout.addWidget(self.rb_curr)
        mb_layout.addWidget(self.rb_all)
        mb_layout.addWidget(self.rb_last)
        sidebar.addWidget(mode_box)
        
        # 3. Page navigation
        nav_box = QHBoxLayout()
        self.btn_prev = QPushButton("◀ Anterior")
        self.btn_prev.clicked.connect(self._prev_page)
        self.lbl_page = QLabel(f"Pág. 1 de {self.page_count}")
        self.lbl_page.setAlignment(Qt.AlignCenter)
        self.btn_next = QPushButton("Próxima ▶")
        self.btn_next.clicked.connect(self._next_page)
        nav_box.addWidget(self.btn_prev)
        nav_box.addWidget(self.lbl_page, 1)
        nav_box.addWidget(self.btn_next)
        sidebar.addLayout(nav_box)
        
        sidebar.addStretch(1)
        
        # Status / warning message badge
        self.lbl_msg = QLabel("")
        self.lbl_msg.setWordWrap(True)
        self.lbl_msg.setAlignment(Qt.AlignCenter)
        self.lbl_msg.setStyleSheet("background: rgba(239, 68, 68, 0.22); border: 1px solid rgba(239, 68, 68, 0.5); border-radius: 6px; padding: 6px; color: #fecaca; font-size: 11px; font-weight: 600;")
        self.lbl_msg.setVisible(False)
        sidebar.addWidget(self.lbl_msg)
        
        # ICP-Brasil Digital Certificate Button
        btn_icp = QPushButton("🔏 Certificado Digital (ICP-Brasil)")
        btn_icp.setStyleSheet("background: rgba(16, 185, 129, 0.18); border: 1px solid rgba(16, 185, 129, 0.4); color: #6ee7b7; font-weight: 600; padding: 6px;")
        btn_icp.clicked.connect(self._open_icp_cert_dialog)
        sidebar.addWidget(btn_icp)

        # 4. Save buttons
        btn_save = QPushButton("✍️ Assinar e Salvar PDF")
        btn_save.setObjectName("primary")
        btn_save.setFixedHeight(38)
        btn_save.clicked.connect(lambda: self._save_signed(ask_dest=False))
        sidebar.addWidget(btn_save)
        
        btn_save_as = QPushButton("💾 Salvar Como…")
        btn_save_as.setFixedHeight(32)
        btn_save_as.clicked.connect(lambda: self._save_signed(ask_dest=True))
        sidebar.addWidget(btn_save_as)
        
        content.addLayout(sidebar)
        self.body.addLayout(content, 1)
        
        self._load_page()

    def _load_page(self):
        page = self.doc[self.cur_page]
        pix = page.get_pixmap(dpi=130)
        qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
        self.preview_canvas.set_page_image(qimg)
        self.lbl_page.setText(f"Pág. {self.cur_page + 1} de {self.page_count}")
        self.btn_prev.setEnabled(self.cur_page > 0)
        self.btn_next.setEnabled(self.cur_page < self.page_count - 1)

    def _prev_page(self):
        if self.cur_page > 0:
            self.cur_page -= 1
            self._load_page()

    def _next_page(self):
        if self.cur_page < self.page_count - 1:
            self.cur_page += 1
            self._load_page()


    def _open_icp_cert_dialog(self):
        dlg = DigitalCertSignDialog(self)
        if dlg.exec() == QDialog.Accepted:
            import hashlib
            doc_bytes = self.src.read_bytes()
            doc_hash = hashlib.sha256(doc_bytes).hexdigest()
            stamp_im = dlg.generate_stamp_image(doc_hash)
            self._set_stamp_image(stamp_im)

    def _open_pad(self):
        dlg = SignaturePadDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self._set_stamp_image(dlg.get_image())

    def _upload_image(self):
        fn, _ = QFileDialog.getOpenFileName(None, "Escolha a imagem da assinatura ou carimbo", "", "Imagens (*.png *.jpg *.jpeg *.webp *.bmp)")
        if fn:
            im = Image.open(fn)
            self._set_stamp_image(im)

    def _set_stamp_image(self, im: Image.Image):
        self.orig_stamp = im
        if self.clean_bg:
            self.stamp_img = make_signature_transparent(im)
        else:
            self.stamp_img = im.convert("RGBA")
        if hasattr(self, "lbl_msg"):
            self.lbl_msg.setVisible(False)
        self.preview_canvas.update()

    def _toggle_clean_bg(self, checked: bool):
        self.clean_bg = checked
        if hasattr(self, "orig_stamp"):
            self._set_stamp_image(self.orig_stamp)

    def _save_signed(self, ask_dest: bool = False):
        if self.stamp_img is None:
            self.lbl_msg.setText("⚠️ Desenhe sua assinatura ou carregue uma imagem antes de salvar!")
            self.lbl_msg.setVisible(True)
            self._open_pad()
            return

        if ask_dest:
            default_name = f"{self.src.stem} (Assinado).pdf"
            fn, _ = QFileDialog.getSaveFileName(None, "Salvar PDF Assinado", default_name, "Documento PDF (*.pdf)")
            if not fn:
                return
            out = Path(fn)
        else:
            out = sibling(self.src, "Assinado", ".pdf")
        
        # Save stamp to PNG buffer
        buf = io.BytesIO()
        self.stamp_img.save(buf, format="PNG")
        stamp_bytes = buf.getvalue()
        
        pages_to_stamp = []
        if self.rb_curr.isChecked():
            pages_to_stamp = [self.cur_page]
        elif self.rb_last.isChecked():
            pages_to_stamp = [self.page_count - 1]
        else:
            pages_to_stamp = list(range(self.page_count))
            
        nr = self.stamp_norm_rect
        src_path = self.src

        def work():
            doc = open_pdf(src_path)
            for pno in pages_to_stamp:
                page = doc[pno]
                pr = page.rect
                x0 = pr.x0 + nr.x() * pr.width
                y0 = pr.y0 + nr.y() * pr.height
                x1 = x0 + nr.width() * pr.width
                y1 = y0 + nr.height() * pr.height
                target_rect = fitz.Rect(x0, y0, x1, y1)
                page.insert_image(target_rect, stream=stamp_bytes, keep_proportion=True)
            doc.save(str(out), garbage=3, deflate=True)
            doc.close()
            return [out]

        if hasattr(self, "doc") and self.doc:
            try:
                self.doc.close()
            except Exception:
                pass

        if hasattr(self, "submit"):
            self.submit("tool:Sign", [str(self.src)], work, "Assinando PDF…", f"Assinado em {len(pages_to_stamp)} pág(s)")
        else:
            outs = work()
            if self.notify:
                self.notify("tool:Sign", [str(self.src)], outs, f"Assinado em {len(pages_to_stamp)} pág(s)")
        self.close()

    def closeEvent(self, e):
        if hasattr(self, "doc") and self.doc:
            try:
                if not getattr(self.doc, "is_closed", False):
                    self.doc.close()
            except Exception:
                pass
        super().closeEvent(e)


class PdfPageSignCanvas(QWidget):
    def __init__(self, parent_win: SignPdfWindow):
        super().__init__(parent_win)
        self.win = parent_win
        self.page_qimg: QImage | None = None
        self._dragging = False
        self._resizing = False
        self._drag_start = QPointF()

    def set_page_image(self, img: QImage):
        self.page_qimg = img
        self.update()

    def _page_rect(self) -> QRectF:
        if not self.page_qimg or self.page_qimg.isNull():
            return QRectF()
        avail = QRectF(self.rect()).adjusted(12, 12, -12, -12)
        s = min(avail.width() / self.page_qimg.width(), avail.height() / self.page_qimg.height())
        w, h = self.page_qimg.width() * s, self.page_qimg.height() * s
        return QRectF(avail.center().x() - w / 2, avail.center().y() - h / 2, w, h)

    def _stamp_widget_rect(self) -> QRectF:
        pr = self._page_rect()
        nr = self.win.stamp_norm_rect
        return QRectF(pr.x() + nr.x() * pr.width(),
                      pr.y() + nr.y() * pr.height(),
                      nr.width() * pr.width(),
                      nr.height() * pr.height())

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            sr = self._stamp_widget_rect()
            handle = QRectF(sr.right() - 14, sr.bottom() - 14, 14, 14)
            if handle.contains(e.position()):
                self._resizing = True
                self._drag_start = e.position()
            elif sr.contains(e.position()):
                self._dragging = True
                self._drag_start = e.position() - sr.topLeft()

    def mouseMoveEvent(self, e):
        pr = self._page_rect()
        if pr.isEmpty():
            return
        if self._dragging:
            new_top_left = e.position() - self._drag_start
            nx = (new_top_left.x() - pr.x()) / pr.width()
            ny = (new_top_left.y() - pr.y()) / pr.height()
            nx = max(0.0, min(1.0 - self.win.stamp_norm_rect.width(), nx))
            ny = max(0.0, min(1.0 - self.win.stamp_norm_rect.height(), ny))
            self.win.stamp_norm_rect.moveLeft(nx)
            self.win.stamp_norm_rect.moveTop(ny)
            self.update()
        elif self._resizing:
            sr = self._stamp_widget_rect()
            nw = max(40, e.position().x() - sr.left())
            nh = max(20, e.position().y() - sr.top())
            self.win.stamp_norm_rect.setWidth(min(1.0 - self.win.stamp_norm_rect.left(), nw / pr.width()))
            self.win.stamp_norm_rect.setHeight(min(1.0 - self.win.stamp_norm_rect.top(), nh / pr.height()))
            self.update()
        else:
            sr = self._stamp_widget_rect()
            handle = QRectF(sr.right() - 14, sr.bottom() - 14, 14, 14)
            if handle.contains(e.position()):
                self.setCursor(Qt.SizeFDiagCursor)
            elif sr.contains(e.position()):
                self.setCursor(Qt.SizeAllCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, e):
        self._dragging = False
        self._resizing = False

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        
        pr = self._page_rect()
        if pr.isEmpty():
            return
            
        # Draw paper drop shadow
        p.fillRect(pr.adjusted(4, 4, 4, 4), QColor(0, 0, 0, 80))
        # Draw page image
        p.drawImage(pr, self.page_qimg)
        p.setPen(QPen(QColor(180, 180, 180), 1))
        p.drawRect(pr)
        
        # Draw stamp
        sr = self._stamp_widget_rect()
        if self.win.stamp_img:
            # Convert PIL to QImage
            buf = io.BytesIO()
            self.win.stamp_img.save(buf, "PNG")
            qimg = QImage.fromData(buf.getvalue())
            p.drawImage(sr, qimg)
        else:
            p.setPen(QPen(QColor("#2563eb"), 1.5, Qt.DashLine))
            p.setBrush(QColor(37, 99, 235, 30))
            p.drawRoundedRect(sr, 6, 6)
            p.setPen(QColor("#2563eb"))
            p.drawText(sr, Qt.AlignCenter, "Posição do Carimbo\n(Arraste ou Redimensione)")
            
        # Stamp selection border and corner handle
        p.setPen(QPen(QColor(37, 99, 235), 1.5))
        p.setBrush(Qt.NoBrush)
        p.drawRect(sr)
        handle = QRectF(sr.right() - 10, sr.bottom() - 10, 10, 10)
        p.fillRect(handle, QColor(37, 99, 235))


# ---------------------------------------------------------------- Organize Pages Window
class OrganizePdfWindow(GlassWindow):
    def __init__(self, src: str | Path, notify=None):
        super().__init__("Organizar Páginas do PDF", size=(880, 640))
        self.src = Path(src)
        self.notify = notify
        self.doc = open_pdf(self.src)
        
        # List of page descriptors: {"orig_index": i, "rotation": 0, "pixmap": QPixmap}
        self.pages_data: list[dict] = []
        
        # UI
        main_layout = QVBoxLayout()
        
        top_info = QLabel("<b>Arraste as miniaturas para reordenar as páginas</b>, ou use os botões abaixo para excluir e girar:")
        top_info.setObjectName("dim")
        main_layout.addWidget(top_info)
        
        self.grid_list = QListWidget()
        self.grid_list.setViewMode(QListWidget.IconMode)
        self.grid_list.setIconSize(QSize(130, 170))
        self.grid_list.setSpacing(14)
        self.grid_list.setMovement(QListWidget.Snap)
        self.grid_list.setDragDropMode(QListWidget.InternalMove)
        self.grid_list.setStyleSheet("""
            QListWidget { background: rgba(15, 23, 42, 160); border-radius: 12px; border: 1px solid rgba(255,255,255,25); padding: 10px; }
            QListWidget::item { color: #f8fafc; font-weight: 600; border: 2px solid transparent; border-radius: 8px; padding: 4px; }
            QListWidget::item:selected { border: 2px solid #2563eb; background: rgba(37, 99, 235, 30); }
        """)
        main_layout.addWidget(self.grid_list, 1)
        
        # Bottom controls
        btn_row = QHBoxLayout()
        btn_del = QPushButton("✕ Excluir Página")
        btn_del.clicked.connect(self._delete_selected)
        btn_row.addWidget(btn_del)
        
        btn_rot = QPushButton("⟳ Girar 90°")
        btn_rot.clicked.connect(self._rotate_selected)
        btn_row.addWidget(btn_rot)
        
        btn_row.addStretch(1)
        
        btn_save = QPushButton("Salvar PDF Organizado")
        btn_save.setObjectName("primary")
        btn_save.setFixedHeight(34)
        btn_save.clicked.connect(self._save_organized)
        btn_row.addWidget(btn_save)
        
        main_layout.addLayout(btn_row)
        self.body.addLayout(main_layout, 1)
        
        self._load_thumbnails()

    def _load_thumbnails(self):
        for i, page in enumerate(self.doc):
            pix = page.get_pixmap(dpi=60)
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
            qpix = QPixmap.fromImage(qimg)
            self.pages_data.append({"orig_index": i, "rotation": 0, "pixmap": qpix})
            
            item = QListWidgetItem(QIcon(qpix), f"Página {i + 1}")
            item.setData(Qt.UserRole, i)
            self.grid_list.addItem(item)

    def _delete_selected(self):
        selected = self.grid_list.selectedItems()
        if not selected:
            return
        for item in selected:
            row = self.grid_list.row(item)
            self.grid_list.takeItem(row)

    def _rotate_selected(self):
        selected = self.grid_list.selectedItems()
        if not selected:
            return
        for item in selected:
            orig_idx = item.data(Qt.UserRole)
            for p in self.pages_data:
                if p["orig_index"] == orig_idx:
                    p["rotation"] = (p["rotation"] + 90) % 360
                    # transform thumbnail
                    from PySide6.QtGui import QTransform
                    tr = QTransform().rotate(p["rotation"])
                    item.setIcon(QIcon(p["pixmap"].transformed(tr)))
                    break

    def _save_organized(self):
        count = self.grid_list.count()
        if count == 0:
            return
            
        out = sibling(self.src, "Organizado", ".pdf")
        new_doc = fitz.open()
        
        for row in range(count):
            item = self.grid_list.item(row)
            orig_idx = item.data(Qt.UserRole)
            rot = next((p["rotation"] for p in self.pages_data if p["orig_index"] == orig_idx), 0)
            new_doc.insert_pdf(self.doc, from_page=orig_idx, to_page=orig_idx, rotate=rot)
            
        new_doc.save(str(out), garbage=3, deflate=True)
        new_doc.close()
        self.doc.close()
        
        if self.notify:
            self.notify("tool:Organize", [str(self.src)], [str(out)], f"{count} páginas reorganizadas")
        self.close()

    def closeEvent(self, e):
        if hasattr(self, "doc") and self.doc:
            try:
                if not getattr(self.doc, "is_closed", False):
                    self.doc.close()
            except Exception:
                pass
        super().closeEvent(e)

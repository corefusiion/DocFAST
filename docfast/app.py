"""DocFAST: Shift+drag any file to convert or edit it from a radial liquid-glass menu."""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QDir, QObject, QPointF, QRunnable, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import (QAction, QColor, QCursor, QDesktopServices, QGuiApplication, QIcon, QPainter,
                           QPixmap)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QSystemTrayIcon, QWidget

from . import __version__, convert, glass, imaging, report, tools, pdf_tools, snipper
from .i18n import t, set_language, get_language
from .radial import Item, RadialMenu
from .settings import Settings, SettingsWindow, WelcomeWindow, TRIGGERS
from .toasts import ToastStack
from .sticky import StickyNoteWindow
from .clipboard_history import ClipboardHistoryManager, ClipboardHistoryWindow
from .snipper import ScreenGifRecorder
from .trigger import DocFASTWatcher
from .util import UserError, category, file_size, human_size, keep, release

APP_NAME = "DocFAST"
KOFI_URL = "https://ko-fi.com/corefusion"
TIP_URL = "https://docfastbr.lovable.app/"
AUTHOR = "Gleisson Santos"
VERSION = __version__
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
from .handoff import ipc_name
IPC_NAME = ipc_name()

GLYPHS = {"Compress": "⇲", "Metadata": "ⓘ", "Redact": "▮", "Crop": "⌗", "Edit": "☼",
          "Annotate": "✎", "Add BG": "▣", "Resize": "⤢", "Split": "✂", "Rotate": "⟳",
          "Merge": "⧉", "Protect": "⚿", "Extract": "⧈", "Sign": "✍", "Organize": "☷",
          "Zip": "🗜", "Zip (Max)": "📦", "Extrair": "📂", "AiChat": "✨"}

HINTS = {
    "Compress": "Reduzir tamanho do arquivo", "Metadata": "Ver · remover GPS", "Redact": "Ocultar informações privadas",
    "Crop": "Cortar em proporções", "Edit": "Luz · cor · rotação", "Annotate": "Setas · textos · passos",
    "Add BG": "Fundo com gradiente", "Resize": "Alterar dimensões", "Split": "Um PDF por página",
    "Rotate": "Girar páginas 90°", "Merge": "Juntar em um só PDF", "Protect": "Adicionar senha",
    "Extract": "Extrair fotos embutidas", "Sign": "Assinar ou carimbar visualmente",
    "Organize": "Reordenar, girar ou excluir páginas",
    "Zip": "Compactar em .zip", "Zip (Max)": "Compressão máxima", "Extrair": "Descompactar arquivos",
    "AiChat": "Analisar com Inteligência Artificial",
}
FORMAT_HINTS = {"JPG": "Small, universal", "PNG": "Lossless · transparency", "WEBP": "Smallest for web",
                "HEIC": "iPhone format", "TIFF": "Print · archival", "AVIF": "Next-gen, tiny",
                "BMP": "Uncompressed", "PDF": "Document", "ICO": "Windows icon", "GIF": "Legacy web",
                "DOCX": "Editable Word", "TXT": "Plain text",
                "XLSX": "Planilha Excel", "CSV": "Valores separados", "JSON": "Dados estruturados", "HTML": "Tabela web",
                "PDF (1 doc)": "Juntar todas em 1 único PDF", "PDF (sep)": "1 PDF individual por imagem"}

IMAGE_TOOLS = ["Compress", "Resize", "Crop", "Edit", "Annotate", "Redact", "Add BG", "Metadata"]
PDF_TOOLS = ["Compress", "Sign", "Organize", "Split", "Rotate", "Protect", "Extract", "Metadata"]


# ---------------------------------------------------------------- background jobs
class _Sig(QObject):
    done = Signal(object)
    failed = Signal(str)


class Job(QRunnable):
    def __init__(self, action: str, srcs: list, fn, extra: str = ""):
        super().__init__()
        self.action, self.srcs, self.fn, self.extra = action, srcs, fn, extra
        self.sig = _Sig()

    def run(self):
        try:
            outs = self.fn() or []
            self.sig.done.emit(report.summarize(self.action, self.srcs, outs, self.extra))
        except UserError as e:
            self.sig.failed.emit(str(e))
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.sig.failed.emit(friendly_error(e))


def friendly_error(e: Exception) -> str:
    msg = str(e) or e.__class__.__name__
    low = msg.lower()
    if isinstance(e, PermissionError) or "permission denied" in low:
        return "No permission to write next to this file. Try a folder you own, or set Settings → Save results → subfolder."
    if "cannot identify image" in low:
        return "This file doesn't look like an image DocFAST can read."
    if isinstance(e, FileNotFoundError):
        return "The file was moved or deleted."
    return msg


# ---------------------------------------------------------------- icon
def make_tray_icon() -> QIcon:
    """macOS menu bar wants a monochrome 'template' image; Windows gets the colour icon."""
    if not IS_MAC:
        return make_icon()
    pm = QPixmap(44, 44)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    from PySide6.QtGui import QPen
    p.setPen(QPen(QColor(0, 0, 0), 4.5))
    p.drawEllipse(QPointF(22, 22), 14, 14)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(0, 0, 0))
    p.drawEllipse(QPointF(22, 22), 5, 5)
    for a in range(0, 360, 45):  # petal gaps
        import math
        x, y = 22 + 14 * math.cos(math.radians(a + 22.5)), 22 + 14 * math.sin(math.radians(a + 22.5))
        p.setCompositionMode(QPainter.CompositionMode_Clear)
        p.drawEllipse(QPointF(x, y), 2.2, 2.2)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    p.end()
    pm.setDevicePixelRatio(2.0)
    icon = QIcon(pm)
    icon.setIsMask(True)
    return icon


def make_icon() -> QIcon:
    ico = Path(__file__).with_name("assets") / "docfast.ico"
    if ico.exists():
        return QIcon(str(ico))
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(glass.iridescent_pen(QPointF(32, 32), 7, 255))
    p.drawEllipse(QPointF(32, 32), 24, 24)
    p.end()
    return QIcon(pm)


# ---------------------------------------------------------------- the app
class DocFASTApp(QObject):
    def __init__(self, qapp: QApplication):
        super().__init__()
        self.qapp = qapp
        self.settings = Settings()
        self.settings.apply()
        self.pool = QThreadPool.globalInstance()
        self.windows: list[QWidget] = []
        self.toasts = ToastStack()
        self.menu = RadialMenu(self.build_rings, self.describe)
        self.menu.activated.connect(self.run_item)

        # the watcher only manages menus it opened (drag mode); click-mode menus (tray, right-click,
        # Send To) must not be closed just because no mouse button is held
        self.watcher = DocFASTWatcher(lambda: self.menu.isVisible() and not self.menu.click_mode,
                                        lambda: self.menu.got_drag, self)
        self.watcher.set_key(self.settings.get("trigger"))
        self.watcher.show_menu.connect(lambda pos: self.menu.popup(pos))
        self.watcher.toggle_ring.connect(self.menu.next_ring)
        self.watcher.hide_menu.connect(self.menu.close_menu)
        self.watcher.excel_ai_triggered.connect(self.start_excel_ai_assistant)
        self.watcher.clipboard_history_triggered.connect(self.open_clipboard_history)
        self.watcher.start()

        # files handed over by "Send to", the right-click menu, or a second launch
        self._pending: list[str] = []
        self._pending_timer = QTimer(self, singleShot=True, interval=280, timeout=self._flush_pending)
        self.server = QLocalServer(self)
        QLocalServer.removeServer(IPC_NAME)
        self.server.listen(IPC_NAME)
        self.server.newConnection.connect(self._ipc)

        self.tray = QSystemTrayIcon(make_tray_icon(), self)
        self.tray.setToolTip(f"{APP_NAME} — press {self.trigger_label()} while dragging a file")
        m = QMenu()
        m.setStyleSheet(glass.QSS)
        self.act_enabled = QAction(t("tray_enabled"), m, checkable=True, checked=True)
        self.act_enabled.toggled.connect(lambda on: setattr(self.watcher, "enabled", on))
        m.addAction(self.act_enabled)
        m.addAction(t("tray_open"), self.open_dialog)
        m.addSeparator()
        m.addAction(t("tray_snip"), self.start_snipping)
        m.addAction(t("tray_clipboard"), self.paste_clipboard)
        m.addSeparator()
        m.addAction("✨ Ajuda AI (Texto selecionado)", lambda: self.ask_ai_on_selection(plus=False))
        m.addAction("📸 Ajuda AI Plus (Texto + Print da Tela)", lambda: self.ask_ai_on_selection(plus=True))
        m.addAction("📊 Especialista em Excel & Planilhas (Ctrl+3)", self.start_excel_ai_assistant)
        m.addSeparator()
        m.addAction("📝 Nova Nota Rápida (Sticky Note)", self.open_sticky_note)
        m.addAction("📋 Histórico da Área de Transferência (Ctrl+Alt+V)", self.open_clipboard_history)
        m.addAction("🎞️ Gravar GIF da Tela (até 15s)", self.start_gif_recording)
        m.addSeparator()
        m.addAction("📊 Status do Sistema & Disco", self.show_system_health)
        m.addSeparator()
        m.addAction(t("tray_settings"), self.open_settings)
        m.addAction(t("tray_help"), self.show_welcome)
        m.addAction("💚 Apoiar no Ko-fi…", lambda: QDesktopServices.openUrl(QUrl(KOFI_URL)))
        m.addAction("🤍 " + t("tray_tip"), lambda: QDesktopServices.openUrl(QUrl(TIP_URL)))
        act_author = m.addAction(t("tray_author"), lambda: QDesktopServices.openUrl(QUrl(TIP_URL)))
        act_author.setToolTip("https://docfastbr.lovable.app/")
        m.addSeparator()
        m.addAction(f"{t('tray_quit')}", self.qapp.quit)
        self.tray_menu = m
        self.tray.setContextMenu(m)
        self.tray.activated.connect(self._tray_click)
        self.tray.show()

        # Clipboard history listener & Sticky Notes restore
        ClipboardHistoryManager.get_instance().attach_listener()
        QTimer.singleShot(600, StickyNoteWindow.restore_all)

        # System health periodic timer
        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self._on_periodic_health)
        self._update_health_timer()
        self.settings.changed.connect(self._update_health_timer)

    def start_snipping(self):
        if hasattr(self, "tray_menu"):
            self.tray_menu.hide()

        def do_capture():
            def on_snip(pix):
                dlg = snipper.SnipActionDialog(pix, self)
                pos = QCursor.pos()
                dlg.move(max(20, pos.x() - 220), max(20, pos.y() - 110))
                self.open_window(dlg)

            self._active_snipper = snipper.ScreenSnipper(on_snip)
            self._active_snipper.show()
            self._active_snipper.raise_()
            self._active_snipper.activateWindow()

        # Brief delay to allow tray menu to fully dismiss before grabbing screenshot
        QTimer.singleShot(200, do_capture)

    def paste_clipboard(self):
        snipper.handle_clipboard_paste(self)

    def ask_ai_on_selection(self, plus: bool = False):
        """Simulate copy on active window to grab selection, then open AI chat."""
        if hasattr(self, "tray_menu"):
            self.tray_menu.hide()

        cb = QApplication.clipboard()
        prev_text = cb.text()

        if IS_WIN:
            try:
                import ctypes
                user32 = ctypes.windll.user32
                user32.keybd_event(0x11, 0, 0, 0)
                user32.keybd_event(0x43, 0, 0, 0)
                user32.keybd_event(0x43, 0, 2, 0)
                user32.keybd_event(0x11, 0, 2, 0)
            except Exception:
                pass

        def proceed():
            new_text = cb.text()
            selected = new_text if (new_text and new_text != prev_text) else ""
            if not selected and prev_text:
                selected = prev_text

            pix = None
            if plus:
                scr = QGuiApplication.primaryScreen()
                if scr:
                    pix = scr.grabWindow(0)

            self.open_ai_chat(initial_text=selected, initial_image=pix)

        QTimer.singleShot(150, proceed)

    def open_ai_chat(self, initial_text: str = "", initial_image: QPixmap | None = None):
        from . import ai_chat
        w = ai_chat.AiChatWindow(self.settings, initial_text=initial_text, initial_image=initial_image)
        self.open_window(w)

    def trigger_label(self) -> str:
        return dict(TRIGGERS).get(self.settings.get("trigger"), "Shift")

    # ------------------------------------------------------------ IPC
    def _ipc(self):
        sock = self.server.nextPendingConnection()
        if sock is None:
            return
        buf = bytearray()
        done = {"v": False}

        def consume():
            if done["v"]:
                return
            try:
                buf.extend(bytes(sock.readAll()))
            except RuntimeError:
                pass
            try:
                data = json.loads(buf.decode("utf-8"))
            except Exception:
                return  # incomplete: wait for more
            done["v"] = True
            files = [f for f in data.get("files", []) if os.path.exists(f)]
            action = data.get("action", "menu")
            print(f"IPC: {len(files)} file(s) handed over [action={action}]", flush=True)
            if files:
                if action == "ai":
                    self.ask_ai_on_files(files)
                elif action == "zip":
                    self.zip_files_direct(files)
                else:
                    self.queue_files(files)
            elif data.get("show"):
                self.toasts.info("DocFAST is already running",
                                 f"Drag any file and press {self.trigger_label()}. It lives in the tray.")
            sock.disconnectFromServer()
            sock.deleteLater()

        # Windows pipes: the sender may already be gone, so read on every signal + a fallback timer
        sock.readyRead.connect(consume)
        sock.disconnected.connect(consume)
        for ms in (0, 50, 200, 600):
            QTimer.singleShot(ms, consume)

    def queue_files(self, files: list[str]):
        """Explorer's right-click menu launches once per file: gather them, then show one menu."""
        for f in files:
            if f not in self._pending:
                self._pending.append(f)
        self._pending_timer.start()

    def _flush_pending(self):
        files, self._pending = self._pending, []
        if files:
            self.show_click_menu(files)

    # ------------------------------------------------------------ menu contents
    def describe(self, paths: list[str]) -> str:
        if len(paths) > 1:
            return f"{len(paths)} files"
        return human_size(file_size(paths[0]))

    def build_rings(self, paths: list[str]) -> dict[str, list[Item]]:
        cat = category(paths[0])
        same = [p for p in paths if category(p) == cat]
        if cat is None or cat in ("generic", "directory", "archive"):
            is_zip = any(str(p).lower().endswith(".zip") for p in paths)
            conv_items = [
                Item("Zip", key="convert:Zip", hint="Compactar em arquivo .zip padrão"),
                Item("Zip (Max)", key="convert:Zip (Max)", hint="Compressão máxima em arquivo .zip"),
            ]
            if is_zip:
                conv_items.append(Item("Extrair", key="convert:Extrair", hint="Descompactar arquivos do .zip"))
            tool_items = [
                Item("Ajuda AI", "✨", key="tool:AiChat", hint="Analisar arquivo ou dúvida com IA")
            ]
            return {"Convert": conv_items, "Tools": tool_items}

        ext = Path(paths[0]).suffix
        convert_items = []
        for t in convert.targets_for(cat, ext, num_files=len(same)):
            hint = FORMAT_HINTS.get(t, "")
            if cat == "image":
                if t == "PDF (1 doc)":
                    hint = f"Juntar {len(same)} imagens em 1 único PDF"
                elif t == "PDF (sep)":
                    hint = f"{len(same)} PDFs separados (1 por imagem)"
                elif len(same) > 1:
                    hint = f"Converter todas ({len(same)}) para {t}"
            elif cat == "sheet":
                if len(same) > 1:
                    hint = f"Converter todas ({len(same)}) para {t}"
            convert_items.append(Item(t, key=f"convert:{t}", hint=hint))
        rings: dict[str, list[Item]] = {"Convert": convert_items}
        if cat == "image":
            rings["Tools"] = [Item(n, GLYPHS[n], key=f"tool:{n}", hint=HINTS[n]) for n in IMAGE_TOOLS] + [
                Item("Ajuda AI", "✨", key="tool:AiChat", hint="Analisar imagem com IA")
            ]
        elif cat == "pdf":
            names = PDF_TOOLS[:3] + (["Merge"] if len(same) > 1 else []) + PDF_TOOLS[3:]
            rings["Tools"] = [Item(n, GLYPHS[n], key=f"tool:{n}", hint=HINTS[n]) for n in names] + [
                Item("Ajuda AI", "✨", key="tool:AiChat", hint="Analisar PDF com IA")
            ]
        elif cat in ("sheet", "docx", "text"):
            rings["Tools"] = [
                Item("Zip", "🗜", key="convert:Zip", hint="Compactar em .zip"),
                Item("Zip (Max)", "📦", key="convert:Zip (Max)", hint="Compressão máxima"),
                Item("Ajuda AI", "✨", key="tool:AiChat", hint="Analisar com IA"),
            ]
        return rings

    # ------------------------------------------------------------ actions
    def run_item(self, item: Item, paths: list[str]):
        cat = category(paths[0])
        paths = [p for p in paths if category(p) == cat]
        kind, name = item.key.split(":", 1)
        if kind == "convert":
            if name in ("Zip", "Zip (Max)"):
                level = 9 if "Max" in name else 6
                self.submit(f"convert:{name}", paths, lambda: convert.zip_files(paths, compress_level=level),
                            f"Compactando {len(paths)} item(ns) em .zip…")
                return
            if name == "Extrair":
                self.submit("convert:Extrair", paths, lambda: convert.extract_archive(paths[0]),
                            "Extraindo arquivos do zip…")
                return
            if cat == "image":
                if name == "PDF (1 doc)":
                    self.submit("convert:PDF (1 doc)", paths, lambda: convert.images_to_single_pdf(paths),
                                f"Juntando {len(paths)} imagens em 1 PDF…")
                elif name in ("PDF (sep)", "PDF"):
                    if len(paths) > 1 and name == "PDF":
                        self.submit("convert:PDF (1 doc)", paths, lambda: convert.images_to_single_pdf(paths),
                                    f"Juntando {len(paths)} imagens em 1 PDF…")
                    else:
                        verb = f"Convertendo {len(paths)} imagens para PDFs separados…" if len(paths) > 1 else "Convertendo para PDF…"
                        self.submit("convert:PDF (sep)", paths,
                                    lambda: [o for p in paths for o in convert.convert(p, cat, "PDF")], verb)
                else:
                    verb = f"Convertendo {len(paths)} imagens para {name}…" if len(paths) > 1 else f"Convertendo para {name}…"
                    self.submit(f"convert:{name}", paths,
                                lambda: [o for p in paths for o in convert.convert(p, cat, name)], verb)
            elif cat == "sheet":
                verb = f"Convertendo {len(paths)} planilha(s) para {name}…" if len(paths) > 1 else f"Convertendo para {name}…"
                self.submit(f"convert:{name}", paths,
                            lambda: [o for p in paths for o in convert.convert(p, cat, name)], verb)
            else:
                verb = f"Converting to {name}…"
                self.submit(f"convert:{name}", paths,
                            lambda: [o for p in paths for o in convert.convert(p, cat, name)], verb)
            return
        if cat == "pdf":
            if name == "Merge":
                self.submit("tool:Merge", paths, lambda: [imaging.merge_pdfs(paths)], "Merging…")
            elif name == "Sign":
                self.open_window(pdf_tools.SignPdfWindow(paths[0], self.notify))
            elif name == "Organize":
                self.open_window(pdf_tools.OrganizePdfWindow(paths[0], self.notify))
            elif name == "Metadata":
                self.open_window(tools.MetadataWindow(paths[0], self.notify, is_pdf=True))
            elif name == "Protect":
                self.open_window(tools.ProtectWindow(paths[0], self.notify))
            else:
                fns = {"Compress": lambda p: [imaging.compress_pdf(p)], "Split": imaging.split_pdf,
                       "Rotate": lambda p: [imaging.rotate_pdf(p)], "Extract": imaging.extract_pdf_images}
                f = fns[name]
                self.submit(f"tool:{name}", paths, lambda: [o for p in paths for o in f(p)],
                            {"Compress": "Compressing…", "Split": "Splitting…", "Rotate": "Rotating…",
                             "Extract": "Extracting images…"}[name])
            return
        if name == "AiChat":
            p0 = Path(paths[0])
            txt_preview = ""
            pix_preview = None
            if p0.is_file() and p0.suffix.lower() in (".txt", ".md", ".json", ".xml", ".csv", ".py", ".log", ".html"):
                try:
                    txt_preview = p0.read_text(encoding="utf-8", errors="ignore")[:2500]
                except Exception:
                    pass
            elif p0.is_file() and p0.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
                pix_preview = QPixmap(str(p0))

            init_text = f"Análise do arquivo '{p0.name}':\n\n{txt_preview}" if txt_preview else f"Análise e dúvidas sobre o arquivo '{p0.name}'."
            self.open_ai_chat(initial_text=init_text, initial_image=pix_preview)
            return

        windows = {"Crop": tools.CropWindow, "Add BG": tools.AddBgWindow, "Annotate": tools.AnnotateWindow,
                   "Redact": tools.RedactWindow, "Edit": tools.EditWindow, "Metadata": tools.MetadataWindow}
        try:
            if name == "Compress":
                self.open_window(tools.CompressWindow(paths, self.notify))
            elif name == "Resize":
                self.open_window(tools.ResizeWindow(paths, self.notify))
            else:
                self.open_window(windows[name](paths[0], self.notify))
        except UserError as e:
            self.toasts.error(f"Couldn't open {name}", str(e))
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.toasts.error(f"Couldn't open {name}", friendly_error(e))

    def open_window(self, w: QWidget):
        if hasattr(w, "submit"):
            w.submit = self.submit
        self.windows.append(w)
        w.destroyed.connect(lambda *_: self.windows.remove(w) if w in self.windows else None)
        if hasattr(w, "present"):
            w.present()
        else:
            w.show()

    def submit(self, action: str, srcs: list, fn, working: str = "Working…", extra: str = ""):
        """Run in the background. A spinner card appears only if it takes > 150 ms."""
        state = {"card": None, "finished": False}
        names = Path(srcs[0]).name if len(srcs) == 1 else f"{len(srcs)} files"

        def show_spinner():
            if not state["finished"]:
                state["card"] = self.toasts.new()
                state["card"].working(working, names)

        QTimer.singleShot(150, show_spinner)
        job = Job(action, srcs, fn, extra)

        def done(r):
            release(job)
            state["finished"] = True
            card = state["card"] or self.toasts.new()
            card.done(r)

        def failed(msg):
            release(job)
            state["finished"] = True
            card = state["card"] or self.toasts.new()
            card.error("Couldn't finish", msg)

        job.sig.done.connect(done)
        job.sig.failed.connect(failed)
        self.pool.start(keep(job))

    def notify(self, action: str, srcs: list, outs: list, extra: str = ""):
        """Called by tool windows after they save."""
        self.toasts.new().done(report.summarize(action, srcs, outs, extra))

    # ------------------------------------------------------------ misc
    def _tray_click(self, reason):
        # macOS: a click on the menu-bar icon shows the menu; Windows: click opens a file
        if not IS_MAC and reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.open_dialog()

    def open_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(None, "Choose file(s) for DocFAST", QDir.homePath())
        if files:
            self.show_click_menu(files)

    def show_click_menu(self, files: list[str]):
        g = (QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()).availableGeometry()
        pos = QCursor.pos() if g.contains(QCursor.pos()) else g.center()
        self.menu.popup(pos, files)
        self.menu.activateWindow()

    def open_settings(self):
        w = SettingsWindow(self.settings)
        w.changed.connect(self._settings_changed)
        self.open_window(w)

    def _settings_changed(self):
        self.watcher.set_key(self.settings.get("trigger"))
        self.tray.setToolTip(f"{APP_NAME} — press {self.trigger_label()} while dragging a file")

    def show_welcome(self):
        self.open_window(WelcomeWindow(self.settings, self.trigger_label()))


class DocFASTQApplication(QApplication):
    """macOS delivers files from Finder's "Open With", the Dock and `open -a` as FileOpen
    events (not argv)."""
    file_opened = Signal(str)

    def __init__(self, argv):
        super().__init__(argv)
        self.early_files: list[str] = []

    def event(self, e):
        from PySide6.QtCore import QEvent
        if e.type() == QEvent.FileOpen:
            f = e.file()
            if f:
                self.early_files.append(f)
                self.file_opened.emit(f)
            return True
        return super().event(e)


def mac_setup(qapp):
    # fonts: util.ui_family picks a real installed family. (Substituting the private
    # ".AppleSystemUIFont" made labels draw nothing on macOS 26.)
    try:
        from . import platform_mac
        platform_mac.become_accessory()
    except Exception:
        pass


def send_to_running(payload: dict) -> bool:
    s = QLocalSocket()
    s.connectToServer(IPC_NAME)
    if not s.waitForConnected(300):
        return False
    s.write(json.dumps(payload).encode("utf-8"))
    s.flush()
    s.waitForBytesWritten(500)
    s.disconnectFromServer()
    return True


def setup_logging():
    """Errors go to %LOCALAPPDATA%\\DocFAST\\log.txt (pythonw / the .exe have no console)."""
    import faulthandler
    if IS_MAC:
        base = Path.home() / "Library" / "Logs" / "DocFAST"
    else:
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "DocFAST"
    base.mkdir(parents=True, exist_ok=True)
    path = base / "log.txt"
    if path.exists() and path.stat().st_size > 1_000_000:
        path.replace(base / "log.old.txt")
    f = open(path, "a", encoding="utf-8", buffering=1)
    f.write(f"\n==== DocFAST {VERSION} started {time.strftime('%Y-%m-%d %H:%M:%S')} ====\n")
    if sys.stderr is None or getattr(sys, "frozen", False) or sys.executable.lower().endswith("pythonw.exe"):
        sys.stdout = sys.stderr = f
    faulthandler.enable(f)

    def hook(t, v, tb):
        f.write("Unhandled: " + "".join(traceback.format_exception(t, v, tb)))
    sys.excepthook = hook
    return path


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    try:
        setup_logging()
    except Exception:
        pass
    if IS_WIN:
        try:  # crisp taskbar/tray icon grouping
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DocFAST.App")
        except Exception:
            pass
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    qapp = DocFASTQApplication(argv)
    if IS_MAC:
        mac_setup(qapp)
    qapp.setApplicationName(APP_NAME)
    qapp.setApplicationVersion(VERSION)
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setWindowIcon(make_icon())

    if "--selftest" in argv:
        return selftest()
    files = [os.path.abspath(a) for a in argv[1:] if not a.startswith("-") and os.path.exists(a)]
    # already running? hand over and exit (instant: no second UI start-up)
    if send_to_running({"files": files} if files else {"show": "--quiet" not in argv}):
        return 0
    app = DocFASTApp(qapp)
    qapp.file_opened.connect(lambda f: app.queue_files([f]))
    if qapp.early_files:
        app.queue_files(list(qapp.early_files))
    if files:  # e.g. "Send to → DocFAST" or drag onto the .exe
        QTimer.singleShot(120, lambda: app.queue_files(files))
    elif not app.settings.get("welcomed"):
        QTimer.singleShot(300, app.show_welcome)
    elif "--quiet" not in argv:
        QTimer.singleShot(400, lambda: app.toasts.info(
            "DocFAST is running", f"Drag any file, then press {app.trigger_label()}."))
    return qapp.exec()




    def start_excel_ai_assistant(self):
        """Grabs active screen and opens AI Chat as a specialized Excel/Data Analyst."""
        if hasattr(self, "tray_menu"):
            self.tray_menu.hide()

        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        pix = screen.grabWindow(0)

        from .ai_chat import AiChatWindow
        if not hasattr(self, "_ai_chat_win") or self._ai_chat_win is None or self._ai_chat_win.isHidden():
            self._ai_chat_win = AiChatWindow(self.settings)

        self._ai_chat_win._set_attached_image(pix)
        prompt = (
            "📊 Olá! Estou analisando esta planilha/tabela na tela. "
            "Por favor, identifique as colunas e sugira as melhores fórmulas "
            "(como PROCX, IFS, SOMASES, tabelas dinâmicas) e correções de dados:"
        )
        self._ai_chat_win.input_edit.setPlainText(prompt)
        self._ai_chat_win.show()
        self._ai_chat_win.raise_()
        self._ai_chat_win.activateWindow()
        # Automatically trigger analysis
        QTimer.singleShot(150, self._ai_chat_win._send_user_message)

    def open_sticky_note(self):
        StickyNoteWindow.create_new()

    def open_clipboard_history(self):
        if not hasattr(self, "_cb_win") or self._cb_win is None or self._cb_win.isHidden():
            self._cb_win = ClipboardHistoryWindow(on_copied=lambda msg: self.toasts.info("Área de Transferência", msg))
        self._cb_win.show()
        self._cb_win.raise_()
        self._cb_win.activateWindow()

    def start_gif_recording(self):
        if hasattr(self, "tray_menu"):
            self.tray_menu.hide()

        def on_saved(gif_path):
            self.toasts.created([gif_path], ["GIF"])

        self._gif_rec = ScreenGifRecorder(on_gif_saved=on_saved)
        self._gif_rec.show()

    def show_system_health(self):
        from .system_card import SystemHealthCard
        if not hasattr(self, "_health_card") or self._health_card is None or self._health_card.isHidden():
            self._health_card = SystemHealthCard()
        self._health_card.show()
        self._health_card.raise_()
        self._health_card.activateWindow()

    def _update_health_timer(self):
        if self.settings.get("system_health_notifications"):
            interval_min = int(self.settings.get("system_health_interval_min") or 60)
            self._health_timer.start(interval_min * 60 * 1000)
        else:
            self._health_timer.stop()

    def _on_periodic_health(self):
        if self.settings.get("system_health_notifications"):
            self.show_system_health()

    def ask_ai_on_files(self, files: list[str]):
        if not files:
            return
        p = Path(files[0])
        from .ai_chat import AiChatWindow
        if not hasattr(self, "_ai_chat_win") or self._ai_chat_win is None or self._ai_chat_win.isHidden():
            self._ai_chat_win = AiChatWindow(self.settings)

        cat = category(p)
        if cat == "image":
            from PySide6.QtGui import QPixmap
            self._ai_chat_win._set_attached_image(QPixmap(str(p)))
            self._ai_chat_win.input_edit.setPlainText(f"Por favor, analise esta imagem '{p.name}':")
        elif cat in ("text", "sheet", "docx"):
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")[:3000]
                self._ai_chat_win.input_edit.setPlainText(f"Por favor, analise o conteúdo de '{p.name}':\n\n```\n{txt}\n```")
            except Exception:
                self._ai_chat_win.input_edit.setPlainText(f"Por favor, ajude-me a analisar o arquivo '{p.name}'.")
        else:
            self._ai_chat_win.input_edit.setPlainText(f"Por favor, explique detalhes e operações úteis para o arquivo '{p.name}'.")

        self._ai_chat_win.show()
        self._ai_chat_win.raise_()
        self._ai_chat_win.activateWindow()

    def zip_files_direct(self, files: list[str]):
        from . import convert
        try:
            res = convert.zip_files(files, compress_level=6)
            self.toasts.created(res, ["Zip"])
        except Exception as e:
            self.toasts.error(f"Erro ao compactar: {e}")


def check_text_renders():
    """Labels must really draw: paint text with the UI fonts and count the inked pixels."""
    from PySide6.QtGui import QImage, QPainter, QColor
    from .util import ui_font, ui_family
    for display in (True, False):
        img = QImage(200, 40, QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        p.setFont(ui_font(16, True, display))
        p.setPen(QColor(255, 255, 255))
        p.drawText(img.rect(), Qt.AlignCenter, "WEBP 43.8 KB")
        p.end()
        inked = sum(1 for y in range(0, 40, 2) for x in range(0, 200, 2) if img.pixelColor(x, y).alpha() > 60)
        print(f"font {ui_family(display)!r}: {inked} inked samples")
        if inked < 30:
            raise RuntimeError(f"text does not render with font {ui_family(display)!r}")


def selftest() -> int:
    """Used by CI on the frozen .exe: exercise every library and build the UI, then exit."""
    import tempfile
    from PIL import Image
    try:
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "t.png"
            Image.new("RGBA", (64, 48), (255, 100, 80, 255)).save(src)
            for t in convert.targets_for("image", ".png"):
                convert.convert(src, "image", t)
            pdf = convert.convert(src, "image", "PDF")[0]
            for t in convert.PDF_TARGETS:
                convert.convert(pdf, "pdf", t)
            (Path(d) / "n.txt").write_text("hello")
            docx = convert.convert(Path(d) / "n.txt", "text", "DOCX")[0]
            convert.convert(docx, "docx", "TXT")
            imaging.add_background(convert.open_image(src), imaging.Background())
            imaging.compress_pdf(pdf)
            imaging.protect_pdf(pdf, "pw")
            from . import liquid
            liquid.render(Image.new("RGB", (80, 80)), liquid.sdf_circle(80, 80, 40, 40, 30))
            menu = RadialMenu(lambda p: {"Convert": [Item("PNG")]}, lambda p: "1 KB")
            menu._load([str(src)])
            n = lambda *a, **k: None
            for w in (tools.CropWindow(str(src), n), tools.AddBgWindow(str(src), n), tools.EditWindow(str(src), n),
                      tools.AnnotateWindow(str(src), n), tools.RedactWindow(str(src), n),
                      tools.MetadataWindow(str(src), n), tools.CompressWindow([str(src)], n),
                      tools.ResizeWindow([str(src)], n), tools.ProtectWindow(str(pdf), n),
                      pdf_tools.SignPdfWindow(str(pdf), n), pdf_tools.OrganizePdfWindow(str(pdf), n)):
                w.close()
            pdf_tools.make_signature_transparent(convert.open_image(src))
            ToastStack().info("ok", "ok").dismiss()
            check_text_renders()
        print("SELFTEST OK")
        return 0
    except Exception:
        traceback.print_exc()
        print("SELFTEST FAILED")
        return 1

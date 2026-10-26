"""DocFAST System Health Card & Windows Context Menu Integrator.
Displays disk usage, recycle bin volume, RAM load, productivity tips,
and manages Windows Explorer context menu entries.
"""
from __future__ import annotations

import ctypes
import os
import shutil
import sys
try:
    import winreg
except ImportError:
    winreg = None
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (QBrush, QColor, QFont, QGuiApplication, QPainter,
                            QPainterPath, QPen)
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
                                QProgressBar, QPushButton, QSizePolicy,
                                QVBoxLayout, QWidget)

from . import glass
from .util import ui_family
from .window import GlassWindow

IS_WIN = sys.platform == "win32"

TIPS = [
    "Pressione Shift duas vezes ao abrir o menu radial para alternar entre Conversão e Ferramentas.",
    "Ao selecionar qualquer texto ou célula no Excel, use 'Ajuda AI' para obter fórmulas e análises na hora.",
    "Copie qualquer texto e use 'Colar da Área de Transferência' para salvar direto no seu Desktop em TXT ou PDF.",
    "Arraste imagens de assinaturas em papel: o DocFAST remove o fundo branco automaticamente.",
    "Selecione múltiplas imagens para juntar em um único PDF sequencial com a opção 'PDF (1 doc)'.",
    "Você pode clicar com o botão direito em pastas para compactar em ZIP instantaneamente.",
]


def get_system_stats() -> dict:
    """Returns disk, memory, recycle bin and tip data."""
    stats = {
        "disk_free_gb": 0.0,
        "disk_total_gb": 0.0,
        "disk_used_pct": 0,
        "ram_used_pct": 0,
        "ram_total_gb": 0.0,
        "ram_free_gb": 0.0,
        "recycle_items": 0,
        "recycle_mb": 0.0,
        "tip": TIPS[hash(os.getpid() + int(QTimer().remainingTime() or 1)) % len(TIPS)],
    }

    # 1. Disk usage (Drive C:)
    try:
        drive = "C:\\" if IS_WIN else "/"
        total, used, free = shutil.disk_usage(drive)
        stats["disk_total_gb"] = round(total / (1024**3), 1)
        stats["disk_free_gb"] = round(free / (1024**3), 1)
        stats["disk_used_pct"] = int((used / total) * 100) if total else 0
    except Exception:
        pass

    # 2. Hardware stats (RAM & CPU)
    if IS_WIN:
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            m_stat = MEMORYSTATUSEX()
            m_stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m_stat)):
                stats["ram_used_pct"] = int(m_stat.dwMemoryLoad)
                stats["ram_total_gb"] = round(m_stat.ullTotalPhys / (1024**3), 1)
                stats["ram_free_gb"] = round(m_stat.ullAvailPhys / (1024**3), 1)
        except Exception:
            pass

    import platform
    stats["cpu_arch"] = platform.machine()
    stats["cpu_count"] = os.cpu_count() or 4
    return stats


# ---------------------------------------------------------------- Windows Context Menu
def _app_exe_path() -> str:
    """Returns the effective executable path to register in Windows Registry."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    python_exe = sys.executable
    run_py = str((Path(__file__).parent.parent / "run.py").resolve())
    return f'"{python_exe}" "{run_py}"'


def is_windows_context_menu_registered() -> bool:
    """Checks if DocFAST right-click entry is present in HKCU."""
    if not IS_WIN:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\*\shell\DocFAST"):
            return True
    except OSError:
        return False


def register_windows_context_menu(enable: bool = True) -> bool:
    """Adds or removes DocFAST actions from Windows Explorer right-click context menu."""
    if not IS_WIN:
        return False

    exe = _app_exe_path()
    icon_path = str((Path(__file__).parent / "assets" / "docfast.ico").resolve()) if (Path(__file__).parent / "assets" / "docfast.ico").exists() else sys.executable

    def delete_key_tree(root, subkey):
        try:
            with winreg.OpenKey(root, subkey, 0, winreg.KEY_ALL_ACCESS) as key:
                while True:
                    try:
                        child = winreg.EnumKey(key, 0)
                        delete_key_tree(root, f"{subkey}\\{child}")
                    except OSError:
                        break
            winreg.DeleteKey(root, subkey)
        except OSError:
            pass

    keys_to_clean = [
        r"Software\Classes\*\shell\DocFAST",
        r"Software\Classes\*\shell\DocFAST.AI",
        r"Software\Classes\*\shell\DocFAST.Zip",
        r"Software\Classes\Directory\shell\DocFAST",
        r"Software\Classes\Directory\shell\DocFAST.Zip",
    ]

    for k in keys_to_clean:
        delete_key_tree(winreg.HKEY_CURRENT_USER, k)

    if not enable:
        return True

    try:
        # 1. File Menu: DocFAST - Menu Radial
        k_radial = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\*\shell\DocFAST")
        winreg.SetValueEx(k_radial, "MUIVerb", 0, winreg.REG_SZ, "DocFAST — Menu Radial")
        winreg.SetValueEx(k_radial, "Icon", 0, winreg.REG_SZ, icon_path)
        k_cmd = winreg.CreateKey(k_radial, "command")
        winreg.SetValueEx(k_cmd, "", 0, winreg.REG_SZ, f'{exe} "%1"')

        # 2. File Menu: DocFAST - Ajuda AI
        k_ai = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\*\shell\DocFAST.AI")
        winreg.SetValueEx(k_ai, "MUIVerb", 0, winreg.REG_SZ, "DocFAST — ✨ Ajuda AI")
        winreg.SetValueEx(k_ai, "Icon", 0, winreg.REG_SZ, icon_path)
        k_ai_cmd = winreg.CreateKey(k_ai, "command")
        winreg.SetValueEx(k_ai_cmd, "", 0, winreg.REG_SZ, f'{exe} --ai "%1"')

        # 3. File Menu: DocFAST - Compactar (Zip)
        k_zip = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\*\shell\DocFAST.Zip")
        winreg.SetValueEx(k_zip, "MUIVerb", 0, winreg.REG_SZ, "DocFAST — 🗜️ Compactar (Zip)")
        winreg.SetValueEx(k_zip, "Icon", 0, winreg.REG_SZ, icon_path)
        k_zip_cmd = winreg.CreateKey(k_zip, "command")
        winreg.SetValueEx(k_zip_cmd, "", 0, winreg.REG_SZ, f'{exe} --zip "%1"')

        # 4. Directory Menu: DocFAST - Compactar Pasta (Zip)
        k_d_zip = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Directory\shell\DocFAST.Zip")
        winreg.SetValueEx(k_d_zip, "MUIVerb", 0, winreg.REG_SZ, "DocFAST — 🗜️ Compactar Pasta (Zip)")
        winreg.SetValueEx(k_d_zip, "Icon", 0, winreg.REG_SZ, icon_path)
        k_d_zip_cmd = winreg.CreateKey(k_d_zip, "command")
        winreg.SetValueEx(k_d_zip_cmd, "", 0, winreg.REG_SZ, f'{exe} --zip "%1"')

        # 5. Directory Menu: DocFAST - Menu Radial
        k_d_rad = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Directory\shell\DocFAST")
        winreg.SetValueEx(k_d_rad, "MUIVerb", 0, winreg.REG_SZ, "DocFAST — Menu Radial")
        winreg.SetValueEx(k_d_rad, "Icon", 0, winreg.REG_SZ, icon_path)
        k_d_rad_cmd = winreg.CreateKey(k_d_rad, "command")
        winreg.SetValueEx(k_d_rad_cmd, "", 0, winreg.REG_SZ, f'{exe} "%1"')

        return True
    except OSError:
        return False


# ---------------------------------------------------------------- Rotating Gear Widget
class RotatingGearIcon(QWidget):
    def __init__(self, size: int = 38, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.angle = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._step)
        self.timer.start(35)  # ~30 fps smooth rotation

    def _step(self):
        self.angle = (self.angle + 2.5) % 360.0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy = self.width() / 2.0, self.height() / 2.0
        r_outer = min(cx, cy) - 2.0
        r_inner = r_outer * 0.58

        p.save()
        p.translate(cx, cy)
        p.rotate(self.angle)

        # Draw elegant gear teeth
        pen = QPen(QColor(90, 200, 255, 230), 2.2)
        p.setPen(pen)
        brush = QBrush(QColor(30, 80, 160, 120))
        p.setBrush(brush)

        teeth = 8
        path = QPainterPath()
        import math
        for i in range(teeth * 2):
            th = (math.pi / teeth) * i
            r = r_outer if i % 2 == 0 else r_inner
            x = r * math.cos(th)
            y = r * math.sin(th)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()
        p.drawPath(path)

        # Center hole
        p.setBrush(QBrush(QColor(15, 23, 42, 220)))
        p.drawEllipse(QPoint(0, 0), int(r_inner * 0.45), int(r_inner * 0.45))
        p.restore()


# ---------------------------------------------------------------- Glass Card Window
class SystemHealthCard(GlassWindow):
    def __init__(self, parent=None):
        super().__init__("Status do Sistema & Saúde do Disco", size=(460, 440))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        stats = get_system_stats()

        header_row = QHBoxLayout()
        gear = RotatingGearIcon(size=40)
        header_row.addWidget(gear)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_h = QLabel("DocFAST · Diagnóstico de Serviço")
        lbl_h.setStyleSheet("font-size: 11.5pt; font-weight: 700; color: #5ac8ff;")
        lbl_sub = QLabel("Monitoramento em tempo real do seu ambiente de trabalho")
        lbl_sub.setObjectName("dim")
        title_box.addWidget(lbl_h)
        title_box.addWidget(lbl_sub)
        header_row.addLayout(title_box, 1)
        self.body.addLayout(header_row)

        self.body.addSpacing(10)

        # 1. Disk Space Card
        disk_box = QFrame()
        disk_box.setStyleSheet("background: rgba(255,255,255,0.06); border-radius: 10px; padding: 10px;")
        db_lay = QVBoxLayout(disk_box)
        db_lay.setSpacing(6)

        d_head = QHBoxLayout()
        lbl_d = QLabel("💾 Disco Local (C:)")
        lbl_d.setStyleSheet("font-weight: 600; font-size: 10pt; color: #ffffff;")
        lbl_d_val = QLabel(f"{stats['disk_free_gb']} GB livres de {stats['disk_total_gb']} GB")
        lbl_d_val.setStyleSheet("color: #8dffb8; font-weight: 600; font-size: 9.5pt;")
        d_head.addWidget(lbl_d)
        d_head.addStretch(1)
        d_head.addWidget(lbl_d_val)
        db_lay.addLayout(d_head)

        bar_disk = QProgressBar()
        bar_disk.setValue(stats["disk_used_pct"])
        bar_disk.setFixedHeight(10)
        bar_disk.setTextVisible(False)
        bar_disk.setStyleSheet("""
            QProgressBar { background: rgba(255,255,255,0.1); border-radius: 5px; }
            QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #5ac8ff, stop:1 #2563eb); border-radius: 5px; }
        """)
        db_lay.addWidget(bar_disk)
        self.body.addWidget(disk_box)

        # 2. RAM and Recycle Bin Row
        two_col = QHBoxLayout()
        two_col.setSpacing(10)

        # RAM
        ram_box = QFrame()
        ram_box.setStyleSheet("background: rgba(255,255,255,0.06); border-radius: 10px; padding: 8px;")
        rb_lay = QVBoxLayout(ram_box)
        lbl_r_title = QLabel("🧠 Memória RAM")
        lbl_r_title.setStyleSheet("font-weight: 600; font-size: 9.5pt; color: #ffffff;")
        lbl_r_val = QLabel(f"{stats['ram_used_pct']}% em uso\n({stats['ram_free_gb']} GB livres)")
        lbl_r_val.setObjectName("dim")
        rb_lay.addWidget(lbl_r_title)
        rb_lay.addWidget(lbl_r_val)
        two_col.addWidget(ram_box, 1)

        # CPU & Architecture
        cpu_box = QFrame()
        cpu_box.setStyleSheet("background: rgba(255,255,255,0.06); border-radius: 10px; padding: 8px;")
        cc_lay = QVBoxLayout(cpu_box)
        lbl_c_title = QLabel("⚡ Processador & Sistema")
        lbl_c_title.setStyleSheet("font-weight: 600; font-size: 9.5pt; color: #ffffff;")
        cores = stats.get("cpu_count", 4)
        arch = stats.get("cpu_arch", "x64")
        lbl_c_val = QLabel(f"{cores} Nucleos ({arch})")
        lbl_c_val.setObjectName("dim")
        cc_lay.addWidget(lbl_c_title)
        cc_lay.addWidget(lbl_c_val)
        two_col.addWidget(cpu_box, 1)

        self.body.addLayout(two_col)

        # 3. Productivity Tip
        tip_box = QFrame()
        tip_box.setStyleSheet("background: rgba(90, 200, 255, 0.08); border-left: 3px solid #5ac8ff; border-radius: 6px; padding: 8px 10px;")
        tb_lay = QVBoxLayout(tip_box)
        tb_lay.setSpacing(4)
        lbl_tip_title = QLabel("💡 Dica de Produtividade")
        lbl_tip_title.setStyleSheet("font-weight: 700; color: #5ac8ff; font-size: 9pt;")
        lbl_tip = QLabel(stats["tip"])
        lbl_tip.setWordWrap(True)
        lbl_tip.setStyleSheet("color: #e2e8f0; font-size: 9.5pt; line-height: 1.3;")
        tb_lay.addWidget(lbl_tip_title)
        tb_lay.addWidget(lbl_tip)
        self.body.addWidget(tip_box)

        self.body.addStretch(1)

        # Buttons footer
        foot = QHBoxLayout()


        foot.addStretch(1)
        btn_close = QPushButton("Fechar")
        btn_close.setObjectName("primary")
        btn_close.clicked.connect(self.close)
        foot.addWidget(btn_close)
        self.body.addLayout(foot)



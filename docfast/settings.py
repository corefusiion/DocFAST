"""Persistent settings + the Settings and Welcome windows."""
from __future__ import annotations

import sys
import threading

from PySide6.QtCore import QSettings, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout,
                                QLabel, QLineEdit, QPushButton, QSlider, QVBoxLayout)

from . import __version__, ai_client, system_card
from .i18n import get_language, set_language, t
from .util import CONFIG
from .window import GlassWindow

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
APP = "DocFAST"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

DEFAULTS = {
    "output": "next",
    "jpg_quality": 90,
    "pdf_dpi": 200,
    "trigger": "shift",
    "language": "pt_BR",
    "theme": "aurora",
    "ai_provider": "gemini",
    "ai_model": "gemini-2.5-flash",
    "ai_api_key": "",
    "ai_base_url": "http://localhost:11434/v1",
    "system_health_notifications": False,
    "system_health_interval_min": 60,
    "welcomed": False,
}


class Settings:
    def __init__(self):
        self.q = QSettings(APP, APP)

    def get(self, key):
        v = self.q.value(key, DEFAULTS.get(key))
        d = DEFAULTS.get(key)
        if isinstance(d, bool):
            return v in (True, "true", "1", 1)
        if isinstance(d, int):
            try:
                return int(v)
            except (TypeError, ValueError):
                return d
        return v

    def set(self, key, value):
        self.q.setValue(key, value)
        self.apply()

    def apply(self):
        for k in ("output", "jpg_quality", "pdf_dpi"):
            CONFIG[k] = self.get(k)
        set_language(self.get("language"))
        from . import glass
        glass.set_theme(self.get("theme"))


# ---------------------------------------------------------------- autostart (Windows)
def launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --quiet'
    return f'"{sys.executable}" -m docfast --quiet'


def autostart_enabled() -> bool:
    if IS_LINUX:
        from . import platform_linux
        return platform_linux.autostart_enabled()
    if IS_MAC:
        from . import platform_mac
        return platform_mac.autostart_enabled()
    if not IS_WIN:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP)
            return True
    except OSError:
        return False


def set_autostart(on: bool):
    if IS_LINUX:
        from . import platform_linux
        platform_linux.set_autostart(on)
        return
    if IS_MAC:
        from . import platform_mac
        platform_mac.set_autostart(on)
        return
    if not IS_WIN:
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(k, APP)
            except OSError:
                pass


TRIGGERS = ([("shift", "Shift ⇧"), ("ctrl", "Control ⌃"), ("alt", "Option ⌥")] if IS_MAC
            else [("shift", "Shift"), ("ctrl", "Ctrl"), ("alt", "Alt")])
LANGS = [("pt_BR", "Português (Brasil)"), ("en", "English")]


class SettingsWindow(GlassWindow):
    changed = Signal()
    test_result_signal = Signal(bool, str)

    def __init__(self, settings: Settings):
        super().__init__(t("settings_title"), size=(560, 680))
        self.s = settings
        self.test_result_signal.connect(self._on_test_result)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        r = 0

        def combo(options, current):
            c = QComboBox()
            for v, label in options:
                c.addItem(label, v)
            idx = max(0, [v for v, _ in options].index(current) if current in [v for v, _ in options] else 0)
            c.setCurrentIndex(idx)
            return c

        # 1. Trigger
        grid.addWidget(QLabel(t("settings_trigger")), r, 0)
        self.trigger = combo(TRIGGERS, self.s.get("trigger"))
        self.trigger.currentIndexChanged.connect(lambda _: self._save("trigger", self.trigger.currentData()))
        grid.addWidget(self.trigger, r, 1)
        r += 1
        hint = QLabel(t("settings_trigger_hint"))
        hint.setObjectName("dim")
        grid.addWidget(hint, r, 1)
        r += 1

        # 2. Output
        outputs = [
            ("next", t("settings_save_next")),
            ("folder", t("settings_save_subfolder")),
        ]
        grid.addWidget(QLabel(t("settings_save")), r, 0)
        self.output = combo(outputs, self.s.get("output"))
        self.output.currentIndexChanged.connect(lambda _: self._save("output", self.output.currentData()))
        grid.addWidget(self.output, r, 1)
        r += 1

        # 3. Theme
        themes = [
            ("aurora", t("theme_aurora")),
            ("dark", t("theme_dark")),
            ("slate", t("theme_slate")),
            ("blue", t("theme_blue")),
            ("mint", t("theme_mint")),
        ]
        grid.addWidget(QLabel(t("settings_theme")), r, 0)
        self.theme = combo(themes, self.s.get("theme"))
        self.theme.currentIndexChanged.connect(self._theme_changed)
        grid.addWidget(self.theme, r, 1)
        r += 1

        # 4. Quality
        grid.addWidget(QLabel(t("settings_quality")), r, 0)
        row = QHBoxLayout()
        self.q = QSlider(Qt.Horizontal)
        self.q.setRange(60, 100)
        self.q.setValue(self.s.get("jpg_quality"))
        self.qv = QLabel(str(self.q.value()))
        self.qv.setObjectName("dim")
        self.qv.setFixedWidth(30)
        self.q.valueChanged.connect(lambda v: (self.qv.setText(str(v)), self._save("jpg_quality", v)))
        row.addWidget(self.q)
        row.addWidget(self.qv)
        grid.addLayout(row, r, 1)
        r += 1

        # 5. DPI
        dpis = [
            (150, t("settings_dpi_150")),
            (200, t("settings_dpi_200")),
            (300, t("settings_dpi_300")),
        ]
        grid.addWidget(QLabel(t("settings_pdf_dpi")), r, 0)
        self.dpi = combo(dpis, self.s.get("pdf_dpi"))
        self.dpi.currentIndexChanged.connect(lambda _: self._save("pdf_dpi", self.dpi.currentData()))
        grid.addWidget(self.dpi, r, 1)
        r += 1

        # 6. Language
        grid.addWidget(QLabel(t("settings_lang")), r, 0)
        self.lang = combo(LANGS, self.s.get("language"))
        self.lang.currentIndexChanged.connect(lambda _: self._save("language", self.lang.currentData()))
        grid.addWidget(self.lang, r, 1)
        r += 1

        # Windows Context Menu Integration
        if IS_WIN:
            self.chk_ctx = QCheckBox("Exibir DocFAST no Menu de Contexto do Botão Direito do Windows")
            self.chk_ctx.setChecked(system_card.is_windows_context_menu_registered())
            self.chk_ctx.toggled.connect(lambda on: system_card.register_windows_context_menu(on))
            grid.addWidget(self.chk_ctx, r, 0, 1, 2)
            r += 1

        # Periodic System Health & Disk Notifications
        health_row = QHBoxLayout()
        self.chk_health = QCheckBox("Alertas periódicos de Saúde do Sistema (Disco, Lixeira e Dicas)")
        self.chk_health.setChecked(self.s.get("system_health_notifications"))
        self.chk_health.toggled.connect(lambda on: self._save("system_health_notifications", on))
        health_row.addWidget(self.chk_health)

        intervals = [("30", "A cada 30 min"), ("60", "A cada 1 hora"), ("120", "A cada 2 horas")]
        self.combo_interval = combo(intervals, str(self.s.get("system_health_interval_min") or "60"))
        self.combo_interval.currentIndexChanged.connect(lambda _: self._save("system_health_interval_min", int(self.combo_interval.currentData())))
        health_row.addWidget(self.combo_interval)
        grid.addLayout(health_row, r, 0, 1, 2)
        r += 1

        # 7. AI Settings Section
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: rgba(255,255,255,0.15); margin: 6px 0;")
        grid.addWidget(sep, r, 0, 1, 2)
        r += 1

        lbl_ai_title = QLabel("✨ Inteligência Artificial (Ajuda AI)")
        lbl_ai_title.setStyleSheet("font-size: 11pt; font-weight: 700; color: #5ac8ff;")
        grid.addWidget(lbl_ai_title, r, 0, 1, 2)
        r += 1

        # AI Provider
        providers = [
            ("gemini", "Google Gemini (Recomendado)"),
            ("openai", "OpenAI (ChatGPT)"),
            ("claude", "Anthropic Claude"),
            ("opencode", "OpenCode / Ollama / Local LLM"),
        ]
        grid.addWidget(QLabel("Provedor LLM"), r, 0)
        self.ai_prov = combo(providers, self.s.get("ai_provider"))
        self.ai_prov.currentIndexChanged.connect(self._ai_provider_changed)
        grid.addWidget(self.ai_prov, r, 1)
        r += 1

        # AI Model
        grid.addWidget(QLabel("Modelo do Chat"), r, 0)
        self.ai_model = QComboBox()
        self._populate_models(self.s.get("ai_provider"), self.s.get("ai_model"))
        self.ai_model.currentIndexChanged.connect(lambda _: self._save("ai_model", self.ai_model.currentText()))
        grid.addWidget(self.ai_model, r, 1)
        r += 1

        # API Key + Link to get key
        grid.addWidget(QLabel("Chave de API (API Key)"), r, 0)
        key_layout = QHBoxLayout()
        self.txt_key = QLineEdit()
        self.txt_key.setEchoMode(QLineEdit.Password)
        self.txt_key.setText(self.s.get("ai_api_key"))
        self.txt_key.setPlaceholderText("Cole sua chave aqui...")
        self.txt_key.textChanged.connect(lambda txt: self._save("ai_api_key", txt.strip()))

        btn_show = QPushButton("👁️")
        btn_show.setFixedSize(30, 26)
        btn_show.setToolTip("Mostrar/Ocultar chave")
        btn_show.clicked.connect(lambda: self.txt_key.setEchoMode(
            QLineEdit.Normal if self.txt_key.echoMode() == QLineEdit.Password else QLineEdit.Password
        ))

        key_layout.addWidget(self.txt_key)
        key_layout.addWidget(btn_show)
        grid.addLayout(key_layout, r, 1)
        r += 1

        # Link to get key
        self.btn_get_key = QPushButton("🔗 Obter Chave de API Gratuita...")
        self.btn_get_key.setStyleSheet("color: #7b8cff; text-align: left; background: transparent; border: none; font-size: 8.5pt; text-decoration: underline;")
        self.btn_get_key.setCursor(Qt.PointingHandCursor)
        self.btn_get_key.clicked.connect(self._open_key_url)
        grid.addWidget(self.btn_get_key, r, 1)
        r += 1

        # Test Connection button + status
        test_layout = QHBoxLayout()
        self.btn_test = QPushButton("⚡ Testar Conexão")
        self.btn_test.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #5ac8ff, stop:1 #2f7bff); font-weight: 700; padding: 4px 12px; border-radius: 8px;")
        self.btn_test.clicked.connect(self._test_ai_connection)
        self.lbl_test_status = QLabel("")
        self.lbl_test_status.setStyleSheet("font-size: 8.5pt; font-weight: 600;")
        test_layout.addWidget(self.btn_test)
        test_layout.addWidget(self.lbl_test_status)
        test_layout.addStretch(1)
        grid.addLayout(test_layout, r, 1)
        r += 1

        # 8. Autostart
        if IS_WIN or IS_MAC or IS_LINUX:
            autostart_label = t("settings_autostart") if IS_WIN else t("settings_autostart_mac")
            self.auto = QCheckBox(autostart_label)
            self.auto.setChecked(autostart_enabled())
            self.auto.toggled.connect(set_autostart)
            grid.addWidget(self.auto, r, 1)
            r += 1

        self.body.addLayout(grid)
        self.body.addStretch(1)

        about = QLabel(t("settings_author_credit", version=__version__))
        about.setObjectName("dim")
        foot = QHBoxLayout()
        foot.addWidget(about)
        foot.addStretch(1)
        done = QPushButton(t("settings_btn_done"))
        done.setObjectName("primary")
        done.clicked.connect(self.close)
        foot.addWidget(done)
        self.body.addLayout(foot)

    def _theme_changed(self, _):
        val = self.theme.currentData()
        self._save("theme", val)
        self.update()

    def _ai_provider_changed(self, _):
        prov = self.ai_prov.currentData()
        self._save("ai_provider", prov)
        info = ai_client.PROVIDERS.get(prov, {})
        default_model = info.get("default_model", "")
        self._populate_models(prov, default_model)
        self._save("ai_model", self.ai_model.currentText())
        self.lbl_test_status.setText("")

    def _populate_models(self, prov: str, select_model: str):
        self.ai_model.blockSignals(True)
        self.ai_model.clear()
        info = ai_client.PROVIDERS.get(prov, ai_client.PROVIDERS["gemini"])
        models = info.get("models", [])
        for m in models:
            self.ai_model.addItem(m)
        idx = models.index(select_model) if select_model in models else 0
        self.ai_model.setCurrentIndex(max(0, idx))
        self.ai_model.blockSignals(False)

    def _open_key_url(self):
        prov = self.ai_prov.currentData()
        info = ai_client.PROVIDERS.get(prov, ai_client.PROVIDERS["gemini"])
        url = info.get("url_key", "https://aistudio.google.com/apikey")
        QDesktopServices.openUrl(QUrl(url))

    def _test_ai_connection(self):
        prov = self.ai_prov.currentData()
        key = self.txt_key.text().strip()
        model = self.ai_model.currentText()
        base_url = self.s.get("ai_base_url")

        self.btn_test.setEnabled(False)
        self.lbl_test_status.setText("Testando conexão...")
        self.lbl_test_status.setStyleSheet("color: #ffd36b; font-size: 8.5pt;")

        def worker():
            ok, msg = ai_client.test_connection(prov, key, model, base_url)
            self.test_result_signal.emit(ok, msg)

        threading.Thread(target=worker, daemon=True).start()

    def _on_test_result(self, ok: bool, msg: str):
        self.btn_test.setEnabled(True)
        if ok:
            self.lbl_test_status.setText("✓ Conectado com sucesso!")
            self.lbl_test_status.setStyleSheet("color: #8dffb8; font-size: 8.5pt; font-weight: 700;")
        else:
            self.lbl_test_status.setText(f"✗ {msg[:40]}...")
            self.lbl_test_status.setToolTip(msg)
            self.lbl_test_status.setStyleSheet("color: #ff6b9d; font-size: 8.5pt; font-weight: 700;")

    def _save(self, key, value):
        self.s.set(key, value)
        self.changed.emit()


class WelcomeWindow(GlassWindow):
    def __init__(self, settings: Settings, trigger_label: str = "Shift"):
        super().__init__("Guia Completo de Uso · DocFAST PRO", size=(680, 660))
        self.s = settings

        subtitle = QLabel("Domine todas as funcionalidades e atalhos de alta produtividade do DocFAST:")
        subtitle.setStyleSheet("color: #94a3b8; font-size: 10pt; margin-bottom: 6px;")
        self.body.addWidget(subtitle)

        guide_items = [
            ("🖱️", "Menu Radial Instantâneo (Arrastar + Tecla)",
             f"Arraste qualquer arquivo ou pasta no Windows Explorer ou Desktop e aperte a tecla <b>{trigger_label}</b>. O menu de vidro surge sob o cursor. Solte o mouse sobre a ação desejada para executar em milissegundos."),

            ("⇄", "Alternar entre Conversão e Ferramentas",
             f"Enquanto o menu radial estiver aberto na tela, toque na tecla <b>{trigger_label}</b> uma segunda vez para alternar instantaneamente entre o anel de formatos de <i>Conversão</i> e o anel de <i>Ferramentas Visuais</i>."),

            ("🧮", "Especialista em Excel & Planilhas (Atalho Ctrl + 3)",
             "Pressione <b>Ctrl + 3</b> enquanto estiver usando o Excel ou visualizando uma tabela na tela. O DocFAST tira um print suave da planilha e abre o chat de IA especializado sugerindo fórmulas (PROCX, IFS, SOMASES, etc.), correções e análises na hora."),

            ("📝", "Notas Rápidas Fixas de Vidro (Sticky Notes)",
             "Crie pequenas notas translúcidas elegantes fixadas na tela (📌) com múltiplas cores suaves para rascunhos de reuniões e tarefas diárias."),

            ("📋", "Histórico Visual da Área de Transferência (Ctrl + Alt + V)",
             "Pressione <b>Ctrl + Alt + V</b> para abrir o painel Liquid-Glass com os últimos 25 itens copiados (textos, links, imagens e tabelas) prontos para colar com 1 clique."),

            ("📄", "Extrair Mídias de Arquivos do Office (.docx, .pptx, .xlsx)",
             "Arraste qualquer apresentação do PowerPoint (.pptx) ou documento do Word (.docx) e selecione <i>Extrair Mídias</i> para extrair todas as fotos e gráficos na resolução nativa máxima."),

            ("🔏", "Certificado Digital ICP-Brasil (.pfx / A1)",
             "Na ferramenta de PDF, clique em <i>Certificado Digital (ICP-Brasil)</i> para carregar seu arquivo .pfx e aplicar o selo oficial com hash SHA-256 e conformidade com a MP 2.200-2/2001."),

            ("🎞️", "Gravar GIFs da Tela (até 15s)",
             "Selecione uma área da tela pelo menu da bandeja e grave tutoriais ou demonstrações de bugs em GIFs ultra-leves (< 2 MB) salvos diretamente no seu Desktop."),
        ]

        for icon_symbol, title, description in guide_items:
            card = QFrame()
            card.setStyleSheet("background: rgba(255,255,255,0.06); border-radius: 8px; padding: 6px 10px; margin-bottom: 4px;")
            c_lay = QHBoxLayout(card)
            c_lay.setContentsMargins(6, 6, 6, 6)
            c_lay.setSpacing(10)

            badge = QLabel(icon_symbol)
            badge.setAlignment(Qt.AlignCenter)
            badge.setFixedSize(32, 32)
            badge.setStyleSheet("background: rgba(90, 200, 255, 0.15); border: 1px solid rgba(90, 200, 255, 0.3); border-radius: 16px; font-size: 13pt;")
            c_lay.addWidget(badge)

            t_box = QVBoxLayout()
            t_box.setSpacing(2)
            lbl_title = QLabel(title)
            lbl_title.setStyleSheet("font-size: 10pt; font-weight: 700; color: #ffffff;")
            lbl_desc = QLabel(description)
            lbl_desc.setWordWrap(True)
            lbl_desc.setStyleSheet("color: #cbd5e1; font-size: 9pt; line-height: 1.3;")
            t_box.addWidget(lbl_title)
            t_box.addWidget(lbl_desc)
            c_lay.addLayout(t_box, 1)

            self.body.addWidget(card)

        self.body.addStretch(1)

        foot = QHBoxLayout()
        if IS_WIN or IS_MAC or IS_LINUX:
            autostart_label = t("settings_autostart") if IS_WIN else t("settings_autostart_mac")
            self.auto = QCheckBox(autostart_label)
            self.auto.setChecked(True)
            foot.addWidget(self.auto)
        foot.addStretch(1)
        ok = QPushButton("Entendi, vamos começar!")
        ok.setObjectName("primary")
        ok.clicked.connect(self._done)
        foot.addWidget(ok)
        self.body.addLayout(foot)

    def _done(self):
        self.s.set("welcomed", True)
        if IS_WIN or IS_MAC or IS_LINUX:
            set_autostart(self.auto.isChecked())
        self.close()

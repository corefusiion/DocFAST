"""DocFAST Internationalization (i18n) module.
Defaults to Portuguese (pt_BR) with full English (en) support.
"""
from __future__ import annotations

LANG = "pt_BR"

STRINGS = {
    "pt_BR": {
        # App & Tray
        "app_title": "DocFAST",
        "tray_tooltip": "DocFAST — arraste qualquer arquivo e pressione {trigger}",
        "tray_enabled": "Ativado",
        "tray_open": "Abrir arquivo…",
        "tray_snip": "Capturar tela (Print)…",
        "tray_clipboard": "Colar da Área de Transferência",
        "tray_settings": "Configurações…",
        "tray_help": "Como usar",
        "tray_tip": "Apoiar o projeto ♥",
        "tray_author": "Criado por Gleisson Santos",
        "tray_quit": "Sair do DocFAST",
        
        # Slices
        "ring_convert": "Converter",
        "ring_tools": "Ferramentas",
        "tool_compress": "Comprimir",
        "tool_resize": "Redimensionar",
        "tool_crop": "Recortar",
        "tool_edit": "Editar",
        "tool_annotate": "Anotar",
        "tool_redact": "Tarjar",
        "tool_add_bg": "Adicionar Fundo",
        "tool_metadata": "Metadados",
        "tool_split": "Dividir",
        "tool_rotate": "Girar",
        "tool_merge": "Mesclar",
        "tool_protect": "Proteger",
        "tool_extract": "Extrair Imagens",
        "tool_sign": "Assinar / Carimbar",
        "tool_organize": "Organizar Páginas",
        
        # Hints
        "hint_compress": "Reduzir tamanho do arquivo",
        "hint_resize": "Alterar dimensões (pixels / %)",
        "hint_crop": "Cortar em proporções livres ou fixas",
        "hint_edit": "Luz, cor, rotação e contraste",
        "hint_annotate": "Setas, caixas, números e textos",
        "hint_redact": "Ocultar informações privadas",
        "hint_add_bg": "Fundo com gradiente e sombra",
        "hint_metadata": "Ver e remover GPS / EXIF",
        "hint_split": "Um PDF individual por página",
        "hint_rotate": "Girar páginas em 90°",
        "hint_merge": "Juntar vários em um só PDF",
        "hint_protect": "Adicionar senha AES-256",
        "hint_extract": "Extrair fotos embutidas",
        "hint_sign": "Assinar ou carimbar visualmente",
        "hint_organize": "Reordenar, girar ou excluir páginas",
        
        # Format hints
        "fmt_jpg": "Pequeno e universal",
        "fmt_png": "Sem perda · com transparência",
        "fmt_webp": "Mais leve para a web",
        "fmt_heic": "Formato de iPhone / Apple",
        "fmt_tiff": "Impressão e arquivamento",
        "fmt_avif": "Nova geração ultra-compacta",
        "fmt_bmp": "Sem compressão",
        "fmt_pdf": "Documento portátil",
        "fmt_ico": "Ícone para Windows",
        "fmt_gif": "Animações simples",
        "fmt_docx": "Documento Word editável",
        "fmt_txt": "Texto simples puro",
        "fmt_xlsx": "Planilha Excel com tabelas",
        "fmt_csv": "Valores separados por vírgula",
        "fmt_json": "Registros estruturados JSON",
        "fmt_html": "Tabela responsiva para web",
        "fmt_pdf_single": "Juntar todas em 1 único PDF",
        "fmt_pdf_sep": "1 PDF individual por imagem",
        
        # Common UI
        "btn_done": "Concluir",
        "btn_save": "Salvar",
        "btn_cancel": "Cancelar",
        "btn_clear": "Limpar",
        "btn_apply": "Aplicar",
        "btn_close": "Fechar",
        "btn_delete": "Excluir",
        "btn_prev": "Anterior",
        "btn_next": "Próxima",
        "btn_page": "Página {cur} de {total}",
        
        # Settings
        "settings_title": "Configurações",
        "settings_trigger": "Abrir o menu com",
        "settings_trigger_hint": "…pressionado enquanto você arrasta um arquivo",
        "settings_save": "Salvar resultados",
        "settings_save_next": "Ao lado do original",
        "settings_save_subfolder": "Em uma subpasta “DocFAST”",
        "settings_quality": "Qualidade JPG / WebP",
        "settings_pdf_dpi": "Resolução de PDF → imagem",
        "settings_lang": "Idioma da interface",
        "settings_autostart": "Iniciar o DocFAST com o Windows",
        "settings_autostart_mac": "Abrir o DocFAST ao fazer login",
    },
    "en": {
        # App & Tray
        "app_title": "DocFAST",
        "tray_tooltip": "DocFAST — drag any file and press {trigger}",
        "tray_enabled": "Enabled",
        "tray_open": "Open a file…",
        "tray_snip": "Screen capture (Print)…",
        "tray_clipboard": "Paste from Clipboard",
        "tray_settings": "Settings…",
        "tray_help": "How to use",
        "tray_tip": "Support the project ♥",
        "tray_author": "Created by Gleisson Santos",
        "tray_quit": "Quit DocFAST",
        
        # Slices
        "ring_convert": "Convert",
        "ring_tools": "Tools",
        "tool_compress": "Compress",
        "tool_resize": "Resize",
        "tool_crop": "Crop",
        "tool_edit": "Edit",
        "tool_annotate": "Annotate",
        "tool_redact": "Redact",
        "tool_add_bg": "Add BG",
        "tool_metadata": "Metadata",
        "tool_split": "Split",
        "tool_rotate": "Rotate",
        "tool_merge": "Merge",
        "tool_protect": "Protect",
        "tool_extract": "Extract",
        "tool_sign": "Sign / Stamp",
        "tool_organize": "Organize Pages",
        
        # Hints
        "hint_compress": "Shrink file size",
        "hint_resize": "Change dimensions",
        "hint_crop": "Trim to a ratio",
        "hint_edit": "Light · colour · rotate",
        "hint_annotate": "Arrows · text · steps",
        "hint_redact": "Hide private info",
        "hint_add_bg": "Gradient backdrop",
        "hint_metadata": "View · remove GPS",
        "hint_split": "One PDF per page",
        "hint_rotate": "Turn pages 90°",
        "hint_merge": "Join into one PDF",
        "hint_protect": "Add a password",
        "hint_extract": "Save embedded images",
        "hint_sign": "Sign or stamp visually",
        "hint_organize": "Reorder, rotate or delete pages",
        
        # Format hints
        "fmt_jpg": "Small, universal",
        "fmt_png": "Lossless · transparency",
        "fmt_webp": "Smallest for web",
        "fmt_heic": "iPhone format",
        "fmt_tiff": "Print · archival",
        "fmt_avif": "Next-gen, tiny",
        "fmt_bmp": "Uncompressed",
        "fmt_pdf": "Document",
        "fmt_ico": "Windows icon",
        "fmt_gif": "Legacy web",
        "fmt_docx": "Editable Word",
        "fmt_txt": "Plain text",
        "fmt_xlsx": "Excel spreadsheet",
        "fmt_csv": "Comma-separated values",
        "fmt_json": "Structured JSON records",
        "fmt_html": "Responsive web table",
        "fmt_pdf_single": "All images combined into 1 PDF",
        "fmt_pdf_sep": "Individual PDF per image",
        
        # Common UI
        "btn_done": "Done",
        "btn_save": "Save",
        "btn_cancel": "Cancel",
        "btn_clear": "Clear",
        "btn_apply": "Apply",
        "btn_close": "Close",
        "btn_delete": "Delete",
        "btn_prev": "Previous",
        "btn_next": "Next",
        "btn_page": "Page {cur} of {total}",
        
        # Settings
        "settings_title": "Settings",
        "settings_trigger": "Open the menu with",
        "settings_trigger_hint": "…pressed while dragging a file",
        "settings_save": "Save results",
        "settings_save_next": "Next to the original",
        "settings_save_subfolder": "In a “DocFAST” subfolder",
        "settings_quality": "JPG / WebP quality",
        "settings_pdf_dpi": "PDF → image resolution",
        "settings_lang": "Interface language",
        "settings_autostart": "Start DocFAST with Windows",
        "settings_autostart_mac": "Open DocFAST at login",
    }
}


def set_language(lang: str):
    global LANG
    if lang in STRINGS:
        LANG = lang


def get_language() -> str:
    return LANG


def t(key: str, **kwargs) -> str:
    val = STRINGS.get(LANG, STRINGS["pt_BR"]).get(key, STRINGS["pt_BR"].get(key, key))
    if kwargs:
        return val.format(**kwargs)
    return val

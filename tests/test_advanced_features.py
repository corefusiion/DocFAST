import io
from pathlib import Path
import pytest
from PIL import Image, ImageDraw

from docfast import convert, pdf_tools
from docfast.i18n import get_language, set_language, t


@pytest.fixture
def pdf_multi_page(tmp_path) -> Path:
    doc = convert.fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), f"Página Original {i + 1}", fontsize=20)
    p = tmp_path / "Documento_Contrato.pdf"
    doc.save(str(p))
    doc.close()
    return p


@pytest.fixture
def sample_signature(tmp_path) -> Path:
    # Simulated signature on white paper
    im = Image.new("RGB", (300, 100), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.line([(20, 50), (100, 30), (180, 70), (280, 40)], fill=(10, 20, 60), width=4)
    p = tmp_path / "minha_assinatura.png"
    im.save(p)
    return p


def test_i18n_translations():
    set_language("pt_BR")
    assert get_language() == "pt_BR"
    assert t("ring_convert") == "Converter"
    assert t("tool_sign") == "Assinar / Carimbar"
    assert t("tool_organize") == "Organizar Páginas"
    assert t("toast_open") == "Abrir"
    assert t("toast_show") == "Mostrar na pasta"
    assert t("toast_undo") == "Desfazer"
    assert t("theme_aurora") == "Aurora Violeta (Padrão)"
    assert t("theme_dark") == "Preto Transparente Glass (Dark)"
    assert t("theme_slate") == "Cinza Suave Translúcido (Slate)"
    assert t("theme_blue") == "Azul Fraco Suave (Sky Blue)"
    assert t("theme_mint") == "Verde Menta Suave (Mint Frost)"

    set_language("en")
    assert get_language() == "en"
    assert t("ring_convert") == "Convert"
    assert t("tool_sign") == "Sign / Stamp"
    assert t("tool_organize") == "Organize Pages"
    assert t("toast_open") == "Open"
    assert t("toast_show") == "Show in folder"
    assert t("toast_undo") == "Undo"

    # Reset to default pt_BR
    set_language("pt_BR")


def test_theme_color_selection():
    from docfast import glass
    assert "aurora" in glass.THEMES
    assert "dark" in glass.THEMES
    assert "slate" in glass.THEMES
    assert "blue" in glass.THEMES
    assert "mint" in glass.THEMES

    glass.set_theme("blue")
    assert glass.get_theme() == "blue"
    tint = glass.current_theme_tint("window")
    assert tint.isValid()

    glass.set_theme("dark")
    assert glass.get_theme() == "dark"

    glass.set_theme("aurora")
    assert glass.get_theme() == "aurora"


def test_signature_background_removal(sample_signature):
    raw_img = Image.open(sample_signature)
    clean_img = pdf_tools.make_signature_transparent(raw_img, threshold=200)
    assert clean_img.mode == "RGBA"

    # Corner was pure white (255, 255, 255) -> should now be transparent (alpha = 0)
    corner_pixel = clean_img.getpixel((0, 0))
    assert corner_pixel[3] == 0

    # Line pixel (100, 30) should have full or near full opacity
    line_pixel = clean_img.getpixel((100, 30))
    assert line_pixel[3] > 200


def test_pdf_signing_execution(pdf_multi_page, sample_signature):
    doc = convert.open_pdf(pdf_multi_page)
    clean_sig = pdf_tools.make_signature_transparent(Image.open(sample_signature))
    
    buf = io.BytesIO()
    clean_sig.save(buf, format="PNG")
    stamp_bytes = buf.getvalue()
    
    # Sign last page at (100, 100, 300, 180)
    last_page = doc[-1]
    target_rect = convert.fitz.Rect(100, 100, 300, 180)
    last_page.insert_image(target_rect, stream=stamp_bytes, keep_proportion=True)
    
    signed_out = pdf_multi_page.with_name("Contrato_Assinado.pdf")
    doc.save(str(signed_out), garbage=3, deflate=True)
    doc.close()
    
    assert signed_out.exists() and signed_out.stat().st_size > 0
    # Verify the signed document opens cleanly
    doc_check = convert.open_pdf(signed_out)
    assert doc_check.page_count == 3
    doc_check.close()


def test_pdf_page_reordering_and_delete(pdf_multi_page):
    doc = convert.open_pdf(pdf_multi_page)
    assert doc.page_count == 3

    # Reorder: page 2, page 0 (delete page 1) and rotate page 2 by 90
    new_doc = convert.fitz.open()
    new_doc.insert_pdf(doc, from_page=2, to_page=2, rotate=90)
    new_doc.insert_pdf(doc, from_page=0, to_page=0, rotate=0)
    
    reordered_out = pdf_multi_page.with_name("Contrato_Reordenado.pdf")
    new_doc.save(str(reordered_out))
    new_doc.close()
    doc.close()

    check = convert.open_pdf(reordered_out)
    assert check.page_count == 2
    assert "Página Original 3" in check[0].get_text()
    assert check[0].rotation == 90
    assert "Página Original 1" in check[1].get_text()
    check.close()


def test_sign_pdf_window_validation(pdf_multi_page):
    from PySide6.QtWidgets import QApplication
    qapp = QApplication.instance() or QApplication([])
    w = pdf_tools.SignPdfWindow(str(pdf_multi_page), notify=lambda *a: None)
    
    # Try saving without signature -> warning label becomes visible, no crash
    assert w.stamp_img is None
    # Monkey patch _open_pad to avoid blocking dialog
    opened = []
    w._open_pad = lambda: opened.append(True)
    w._save_signed(ask_dest=False)
    
    assert not w.lbl_msg.isHidden()
    assert "⚠️" in w.lbl_msg.text()
    assert len(opened) == 1
    w.close()


def test_snipper_actions(tmp_path):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QPixmap, QColor
    from docfast import snipper
    qapp = QApplication.instance() or QApplication([])
    
    # Create test pixmap
    pm = QPixmap(100, 80)
    pm.fill(QColor("blue"))
    
    dlg = snipper.SnipActionDialog(pm, app_ref=None)
    assert dlg.pix.width() == 100
    assert dlg.pix.height() == 80
    
    tmp_png = dlg._temp_png_path()
    assert tmp_png.exists() and tmp_png.stat().st_size > 0
    dlg.close()


def test_zip_and_extract(tmp_path):
    f1 = tmp_path / "arquivo1.txt"
    f1.write_text("Conteudo do arquivo 1", encoding="utf-8")
    f2 = tmp_path / "planilha.csv"
    f2.write_text("a,b,c\n1,2,3\n", encoding="utf-8")

    # Zip normal via convert dispatch
    res = convert.convert(f1, "generic", "Zip")
    assert len(res) == 1
    assert res[0].exists() and res[0].suffix == ".zip"

    # Zip max
    res_max = convert.convert(f1, "generic", "Zip (Max)")
    assert len(res_max) == 1
    assert res_max[0].exists()

    # Extract
    extracted = convert.convert(res[0], "archive", "Extrair")
    assert len(extracted) >= 1
    assert any(p.name == "arquivo1.txt" for p in extracted)


def test_desktop_dir_and_ai_client():
    from docfast.util import desktop_dir
    from docfast import ai_client

    desk = desktop_dir()
    assert desk.exists()
    assert desk.is_dir()

    # Verify AI Providers catalog
    assert "gemini" in ai_client.PROVIDERS
    assert "openai" in ai_client.PROVIDERS
    assert "claude" in ai_client.PROVIDERS
    assert "opencode" in ai_client.PROVIDERS

    gemini_models = ai_client.PROVIDERS["gemini"]["models"]
    assert "gemini-2.5-flash" in gemini_models
    assert "gemini-2.5-pro" in gemini_models

    # Test connection error handling with invalid key
    success, msg = ai_client.test_connection("gemini", "fake-key", "gemini-2.5-flash")
    assert success is False
    assert len(msg) > 0

    # Test history path from ai_chat
    from docfast import ai_chat
    hist_p = ai_chat.history_file_path()
    assert hist_p.name == "ai_chat_history.json"



def test_system_card_and_welcome():
    from docfast import system_card
    from docfast.settings import Settings, WelcomeWindow
    from PySide6.QtWidgets import QApplication

    qapp = QApplication.instance() or QApplication([])

    # Test system stats dictionary
    stats = system_card.get_system_stats()
    assert "disk_free_gb" in stats
    assert "disk_total_gb" in stats
    assert "tip" in stats
    assert len(stats["tip"]) > 0

    # Test RotatingGear widget
    gear = system_card.RotatingGearIcon(size=30)
    assert gear.width() == 30
    gear.close()

    # Test WelcomeWindow detailed guide
    s = Settings()
    w = WelcomeWindow(s, trigger_label="Shift")
    assert w.windowTitle() != ""
    w.close()



def test_office_media_extraction(tmp_path):
    import zipfile
    from PIL import Image
    from docfast import convert

    # Create dummy docx with image in word/media/
    docx_file = tmp_path / "Documento_Teste.docx"
    with zipfile.ZipFile(docx_file, "w") as zf:
        zf.writestr("word/document.xml", "<w:document></w:document>")
        buf = io.BytesIO()
        Image.new("RGB", (60, 60), (255, 120, 0)).save(buf, format="PNG")
        zf.writestr("word/media/logo_empresa.png", buf.getvalue())

    extracted = convert.extract_office_media(docx_file)
    assert len(extracted) == 1
    assert extracted[0].exists()
    assert extracted[0].name == "logo_empresa.png"


def test_sticky_notes_and_clipboard_history():
    from docfast import sticky, clipboard_history
    from PySide6.QtWidgets import QApplication

    qapp = QApplication.instance() or QApplication([])

    # Test StickyNote creation
    note = sticky.StickyNoteWindow(content="Minha nota corporativa")
    assert note.editor.toPlainText() == "Minha nota corporativa"
    note._save_to_disk()
    notes = sticky.load_all_notes()
    assert any(n["id"] == note.note_id for n in notes)
    note._delete_note()

    # Test Clipboard History Manager
    mgr = clipboard_history.ClipboardHistoryManager.get_instance()
    mgr.items.insert(0, {"id": "1", "type": "text", "text": "Teste de Copia"})
    assert len(mgr.items) >= 1
    w_clip = clipboard_history.ClipboardHistoryWindow()
    assert w_clip.windowTitle() != ""
    w_clip.close()


def test_icp_brasil_cert_stamp():
    from docfast import pdf_tools
    from PySide6.QtWidgets import QApplication

    qapp = QApplication.instance() or QApplication([])

    dlg = pdf_tools.DigitalCertSignDialog()
    dlg.cert_info = {
        "name": "Gleisson Santos",
        "issuer": "AC SERPRO ICP-Brasil",
        "date": "24/10/2026 12:00:00"
    }
    stamp_im = dlg.generate_stamp_image("dummy_sha256_hash")
    assert stamp_im.size == (480, 160)
    assert stamp_im.mode == "RGBA"
    dlg.close()



def test_lan_broadcast_and_scheduler():
    from docfast import lan_broadcast
    from PySide6.QtWidgets import QApplication

    qapp = QApplication.instance() or QApplication([])

    # Test broadcasting a packet
    sent = lan_broadcast.broadcast_message("DSS - Seguranca", "Mensagem de teste de seguranca")
    assert sent is True

    # Test scheduler storage
    test_ann = [{"id": "t1", "title": "DSS Teste", "message": "Hora do DSS", "trigger_dt": "2026-10-24 15:00"}]
    lan_broadcast.save_scheduled(test_ann)
    loaded = lan_broadcast.load_scheduled()
    assert any(it["id"] == "t1" for it in loaded)

    # Test toast widget
    toast = lan_broadcast.LanNoticeToast({
        "title": "DSS Teste",
        "sender_name": "Gleisson",
        "sender_host": "PC-TEST",
        "message": "Nosso DSS e amanha as 08:15",
        "icon": "🛡️"
    })
    assert "DSS Teste" in toast.windowTitle()
    toast.close()



def test_docfast_app_instantiation():
    from docfast.app import DocFASTApp, DocFASTQApplication
    from PySide6.QtWidgets import QApplication

    qapp = QApplication.instance() or DocFASTQApplication(["DocFAST", "--quiet"])
    app = DocFASTApp(qapp)
    assert hasattr(app, "start_excel_ai_assistant")
    assert hasattr(app, "open_sticky_note")
    assert hasattr(app, "open_clipboard_history")
    assert hasattr(app, "open_lan_broadcast_dialog")
    assert hasattr(app, "show_system_health")
    assert hasattr(app, "start_gif_recording")

    # Clean teardown for CI runner stability
    if hasattr(app, "watcher") and hasattr(app.watcher, "timer"):
        app.watcher.timer.stop()
    if hasattr(app, "_sched_timer"):
        app._sched_timer.stop()
    if hasattr(app, "_health_timer"):
        app._health_timer.stop()
    if hasattr(app, "lan_listener"):
        app.lan_listener.stop_listening()
    if hasattr(app, "server"):
        app.server.close()

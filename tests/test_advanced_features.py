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

    set_language("en")
    assert get_language() == "en"
    assert t("ring_convert") == "Convert"
    assert t("tool_sign") == "Sign / Stamp"
    assert t("tool_organize") == "Organize Pages"

    # Reset to default pt_BR
    set_language("pt_BR")


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

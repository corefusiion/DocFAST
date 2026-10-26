import io
import json
from pathlib import Path
import pytest
from PIL import Image

from docfast import data_convert, safe_trash, history, watch, sticky, snipper
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QColor


@pytest.fixture
def sample_json(tmp_path) -> Path:
    p = tmp_path / "dados.json"
    data = [
        {"nome": "Ana Silva", "cargo": "Engenheira", "salario": 12500},
        {"nome": "Carlos Souza", "cargo": "Analista", "salario": 8400},
        {"nome": "Beatriz Lima", "cargo": "Diretora", "salario": 21000},
    ]
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p


def test_data_convert_json_to_csv_and_xlsx(sample_json):
    records = data_convert.read_data_records(sample_json)
    assert len(records) == 3
    assert records[0]["nome"] == "Ana Silva"

    # CSV
    csv_out = sample_json.with_suffix(".csv")
    data_convert.records_to_csv(records, csv_out)
    assert csv_out.exists()
    assert "Ana Silva" in csv_out.read_text(encoding="utf-8")

    # XLSX
    xlsx_out = sample_json.with_suffix(".xlsx")
    data_convert.records_to_xlsx(records, xlsx_out)
    assert xlsx_out.exists() and xlsx_out.stat().st_size > 0

    # Markdown Table
    md_out = sample_json.with_suffix(".md")
    data_convert.records_to_markdown_table(records, md_out)
    assert md_out.exists()
    assert "| Ana Silva |" in md_out.read_text(encoding="utf-8")

    # YAML
    yaml_out = sample_json.with_suffix(".yaml")
    data_convert.records_to_yaml(records, yaml_out)
    assert yaml_out.exists()
    assert "Engenheira" in yaml_out.read_text(encoding="utf-8")

    # XML
    xml_out = sample_json.with_suffix(".xml")
    data_convert.records_to_xml(records, xml_out)
    assert xml_out.exists()
    assert "<nome>Ana Silva</nome>" in xml_out.read_text(encoding="utf-8")


def test_safe_trash_and_only_if_smaller(tmp_path):
    f_orig = tmp_path / "arquivo_original.txt"
    f_orig.write_text("conteudo original de teste", encoding="utf-8")

    # Test only_if_smaller
    f_smaller = tmp_path / "arquivo_menor.txt"
    f_smaller.write_text("menor", encoding="utf-8")

    f_larger = tmp_path / "arquivo_maior.txt"
    f_larger.write_text("conteudo muito maior que o arquivo original de teste", encoding="utf-8")

    # Smaller is kept
    kept = safe_trash.verify_only_if_smaller(f_orig, [f_smaller])
    assert kept == [f_smaller]

    # Larger is discarded
    discarded = safe_trash.verify_only_if_smaller(f_orig, [f_larger])
    assert not f_larger.exists()


def test_conversion_history(tmp_path):
    src = tmp_path / "orig.png"
    src.write_bytes(b"1234567890" * 100)

    out = tmp_path / "dest.webp"
    out.write_bytes(b"12345" * 20)

    history.record_conversion(src, [out], cat="image")
    entries = history.load_history()
    assert len(entries) >= 1
    assert entries[0]["src_name"] == "orig.png"
    assert entries[0]["out_name"] == "dest.webp"
    assert entries[0]["ratio"] > 0


def test_watch_folder_rules(tmp_path):
    folder = tmp_path / "watch_inbox"
    folder.mkdir()

    rules = [{
        "folder": str(folder),
        "target": "PDF",
        "action_after": "keep",
        "enabled": True
    }]
    watch.save_watch_rules(rules)
    loaded = watch.load_watch_rules()
    assert any(r["folder"] == str(folder) for r in loaded)


def test_sticky_notes_startup_limit():
    qapp = QApplication.instance() or QApplication([])

    # Ensure multiple notes in data doesn't open more than 1
    sample_notes = [
        {"id": "n1", "content": "Nota 1", "x": 100, "y": 100},
        {"id": "n2", "content": "Nota 2", "x": 200, "y": 200},
        {"id": "n3", "content": "Nota 3", "x": 300, "y": 300},
    ]
    sticky.save_all_notes(sample_notes)
    # Clear active instances
    for inst in list(sticky.StickyNoteWindow.active_instances):
        inst.close()
    sticky.StickyNoteWindow.active_instances.clear()

    sticky.StickyNoteWindow.restore_all()
    assert len(sticky.StickyNoteWindow.active_instances) <= 1
    for inst in list(sticky.StickyNoteWindow.active_instances):
        inst.close()


def test_gif_recorder_frame_capture():
    qapp = QApplication.instance() or QApplication([])
    rec = snipper.ScreenGifRecorder()
    rec.selected_rect = rec.rect()

    # Simulate single frame capture
    rec._capture_frame()
    # At least check no exception raised and recorder closes cleanly
    rec.close()

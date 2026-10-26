"""Universal Structured Data Converter for DocFAST.
Bidirectional conversions between JSON, CSV, TSV, YAML, XML, XLSX, and Markdown Tables.
"""
from __future__ import annotations

import csv
import html
import io
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from .util import unique_path, sibling

DATA_EXTS = {".json", ".csv", ".tsv", ".yaml", ".yml", ".xml"}


# ---------------------------------------------------------------- Readers
def read_data_records(src: Path) -> list[dict]:
    """Reads structured records from JSON, CSV, TSV, YAML, or XML."""
    ext = src.suffix.lower()

    if ext == ".json":
        text = src.read_text(encoding="utf-8", errors="ignore")
        data = json.loads(text)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            # Check if dict wraps a list (e.g. {"data": [...]} or {"items": [...]})
            for v in data.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    return v
            return [data]
        return [{"value": str(data)}]

    if ext in (".csv", ".tsv"):
        text = src.read_text(encoding="utf-8", errors="ignore")
        delim = "\t" if ext == ".tsv" else (";" if ";" in text.splitlines()[0] and "," not in text.splitlines()[0] else ",")
        reader = csv.DictReader(text.splitlines(), delimiter=delim)
        return [dict(row) for row in reader if any(v.strip() for v in row.values() if v)]

    if ext in (".yaml", ".yml"):
        # Simple pure Python YAML reader for common key-value lists
        records: list[dict] = []
        cur: dict = {}
        text = src.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s.startswith("- "):
                if cur:
                    records.append(cur)
                    cur = {}
                s = s[2:].strip()
            if ":" in s:
                k, v = s.split(":", 1)
                cur[k.strip().strip("'\"")] = v.strip().strip("'\"")
        if cur:
            records.append(cur)
        return records

    if ext == ".xml":
        tree = ET.parse(src)
        root = tree.getroot()
        records = []
        for child in root:
            row = {}
            for sub in child:
                row[sub.tag] = (sub.text or "").strip()
            if row:
                records.append(row)
            elif child.attrib:
                records.append(dict(child.attrib))
        return records

    return []


# ---------------------------------------------------------------- Writers
def records_to_csv(records: list[dict], out_path: Path, delimiter: str = ",") -> Path:
    if not records:
        out_path.write_text("", encoding="utf-8")
        return out_path
    keys = list(dict.fromkeys(k for r in records for k in r.keys()))
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=keys, delimiter=delimiter)
    writer.writeheader()
    for r in records:
        writer.writerow({k: r.get(k, "") for k in keys})
    out_path.write_text(buf.getvalue(), encoding="utf-8")
    return out_path


def records_to_json(records: list[dict], out_path: Path) -> Path:
    content = json.dumps(records, indent=2, ensure_ascii=False)
    out_path.write_text(content, encoding="utf-8")
    return out_path


def records_to_yaml(records: list[dict], out_path: Path) -> Path:
    lines = []
    for r in records:
        first = True
        for k, v in r.items():
            prefix = "- " if first else "  "
            first = False
            clean_v = str(v).replace("\n", " ")
            lines.append(f"{prefix}{k}: \"{clean_v}\"")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def records_to_xml(records: list[dict], out_path: Path) -> Path:
    root = ET.Element("data")
    for r in records:
        item = ET.SubElement(root, "record")
        for k, v in r.items():
            tag = "".join(c if c.isalnum() or c == "_" else "_" for c in str(k))
            if not tag or tag[0].isdigit():
                tag = f"field_{tag}"
            child = ET.SubElement(item, tag)
            child.text = str(v)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(str(out_path), encoding="utf-8", xml_declaration=True)
    return out_path


def records_to_markdown_table(records: list[dict], out_path: Path) -> Path:
    if not records:
        out_path.write_text("", encoding="utf-8")
        return out_path
    keys = list(dict.fromkeys(k for r in records for k in r.keys()))
    header = "| " + " | ".join(keys) + " |"
    sep = "| " + " | ".join("---" for _ in keys) + " |"
    rows = [header, sep]
    for r in records:
        row_str = "| " + " | ".join(str(r.get(k, "")).replace("|", "\\|").replace("\n", " ") for k in keys) + " |"
        rows.append(row_str)
    out_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return out_path


def records_to_xlsx(records: list[dict], out_path: Path) -> Path:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Dados"

    if not records:
        wb.save(str(out_path))
        return out_path

    keys = list(dict.fromkeys(k for r in records for k in r.keys()))

    # Modern header style
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Segoe UI", size=10)
    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    ws.append(keys)
    for col_idx in range(1, len(keys) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for r in records:
        ws.append([r.get(k, "") for k in keys])

    for row in ws.iter_rows(min_row=2, max_row=len(records) + 1, min_col=1, max_col=len(keys)):
        for cell in row:
            cell.font = data_font
            cell.border = thin_border

    # Auto fit column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 40)

    wb.save(str(out_path))
    return out_path


def convert_data(src: str | Path, target_format: str) -> list[Path]:
    """Converts structured data file into target_format."""
    src = Path(src)
    records = read_data_records(src)
    target = target_format.upper().replace(" ", "")

    ext_map = {
        "CSV": (".csv", lambda r, p: records_to_csv(r, p, delimiter=",")),
        "TSV": (".tsv", lambda r, p: records_to_csv(r, p, delimiter="\t")),
        "JSON": (".json", records_to_json),
        "YAML": (".yaml", records_to_yaml),
        "XML": (".xml", records_to_xml),
        "XLSX": (".xlsx", records_to_xlsx),
        "MARKDOWN": (".md", records_to_markdown_table),
        "MDTABLE": (".md", records_to_markdown_table),
    }

    if target not in ext_map:
        raise ValueError(f"Formato de dados desconhecido: {target_format}")

    ext, writer = ext_map[target]
    out_file = sibling(src, ext=ext)
    writer(records, out_file)
    return [out_file]

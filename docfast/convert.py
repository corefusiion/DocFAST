"""Format conversions. Every function takes a source path and returns a list of
output paths written next to the source."""
from __future__ import annotations

import html
import io
import os
import sys
from pathlib import Path

from PIL import Image, ImageOps

from .util import UserError, sibling

try:  # HEIC / HEIF support
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_OK = True
except Exception:  # pragma: no cover
    HEIF_OK = False

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz  # type: ignore

IMAGE_TARGETS = ["PNG", "JPG", "WEBP", "HEIC", "TIFF", "AVIF", "BMP", "PDF", "ICO", "GIF"]
PDF_TARGETS = ["JPG", "PNG", "DOCX", "TXT"]
DOCX_TARGETS = ["PDF", "TXT"]
TEXT_TARGETS = ["PDF", "DOCX"]
DATA_TARGETS = ["XLSX", "CSV", "JSON", "YAML", "XML", "MD Table"]

PIL_FORMAT = {"PNG": "PNG", "JPG": "JPEG", "WEBP": "WEBP", "HEIC": "HEIF", "TIFF": "TIFF",
              "AVIF": "AVIF", "BMP": "BMP", "PDF": "PDF", "ICO": "ICO", "GIF": "GIF"}
NO_ALPHA = {"JPG", "PDF", "BMP"}


# ---------------------------------------------------------------- images
def open_image(path: str | Path) -> Image.Image:
    im = Image.open(path)
    im.seek(0)
    im = ImageOps.exif_transpose(im)  # honour camera rotation
    if im.mode in ("P", "LA", "PA"):
        im = im.convert("RGBA")
    elif im.mode not in ("RGB", "RGBA", "L"):
        im = im.convert("RGB")
    return im


def open_preview(path: str | Path, max_side: int = 1400) -> Image.Image:
    """Fast, reduced-size decode for on-screen previews (JPEG decodes at 1/2, 1/4, 1/8 scale)."""
    im = Image.open(path)
    im.seek(0)
    if im.format == "JPEG":
        im.draft("RGB", (max_side, max_side))
    im = ImageOps.exif_transpose(im)
    if im.mode in ("P", "LA", "PA"):
        im = im.convert("RGBA")
    elif im.mode not in ("RGB", "RGBA", "L"):
        im = im.convert("RGB")
    if max(im.size) > max_side:
        im.thumbnail((max_side, max_side), Image.LANCZOS)
    return im


def open_pdf(path: str | Path):
    doc = fitz.open(path)
    if doc.needs_pass:
        doc.close()
        raise UserError("This PDF is password-protected. Remove the password first.")
    return doc


def flatten(im: Image.Image, bg=(255, 255, 255)) -> Image.Image:
    if im.mode == "RGBA":
        base = Image.new("RGB", im.size, bg)
        base.paste(im, mask=im.split()[3])
        return base
    return im.convert("RGB") if im.mode != "RGB" else im


def save_image(im: Image.Image, out: Path, target: str, quality: int | None = None, exif=None) -> None:
    from .util import CONFIG
    quality = quality or int(CONFIG.get("jpg_quality", 90))
    target = target.upper()
    fmt = PIL_FORMAT[target]
    if target in NO_ALPHA:
        im = flatten(im)
    kw: dict = {}
    if target in ("JPG", "WEBP", "AVIF", "HEIC"):
        kw["quality"] = quality
    if target == "JPG":
        kw.update(optimize=True, progressive=True)
    if target == "PNG":
        kw["optimize"] = True
    if target == "ICO":
        side = min(256, max(im.size))
        im = ImageOps.contain(im.convert("RGBA"), (side, side))
        kw["sizes"] = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256) if s <= side]
    if target == "PDF":
        kw["resolution"] = 150.0
    if exif and target in ("JPG", "WEBP", "PNG", "TIFF"):
        kw["exif"] = exif
    atomic_save(lambda dst: im.save(dst, fmt, **kw), out)


def atomic_save(write, out):
    """Write to a hidden temp file, then rename: Explorer never shows a half-written file."""
    import os
    if not isinstance(out, (str, Path)):
        write(out)  # in-memory buffer
        return
    out = Path(out)
    tmp = out.with_name(f".~{out.name}.part")
    try:
        write(tmp)
        os.replace(tmp, out)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def image_to(src: str | Path, target: str) -> list[Path]:
    target = target.upper()
    im = open_image(src)
    out = sibling(src, ext="." + target.lower())
    save_image(im, out, target)
    return [out]


def images_to_single_pdf(srcs: list[str | Path]) -> list[Path]:
    pages = [flatten(open_image(s)) for s in srcs]
    out = sibling(srcs[0], "Combined", ".pdf")
    pages[0].save(out, "PDF", resolution=150.0, save_all=True, append_images=pages[1:])
    return [out]


# ---------------------------------------------------------------- PDF
def pdf_to_images(src: str | Path, target: str, dpi: int | None = None) -> list[Path]:
    from .util import CONFIG
    dpi = dpi or int(CONFIG.get("pdf_dpi", 200))
    target = target.upper()
    outs = []
    with open_pdf(src) as doc:
        n = doc.page_count
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            label = f"page {i + 1}" if n > 1 else ""
            out = sibling(src, label, "." + target.lower())
            save_image(im, out, target)
            outs.append(out)
    return outs


def pdf_to_txt(src: str | Path) -> list[Path]:
    with open_pdf(src) as doc:
        text = "\n\f\n".join(page.get_text("text") for page in doc)
    out = sibling(src, ext=".txt")
    out.write_text(text, encoding="utf-8")
    return [out]


def pdf_to_docx(src: str | Path) -> list[Path]:
    """Text blocks become paragraphs, embedded images are kept, one Word page per PDF page."""
    from docx import Document
    from docx.enum.text import WD_BREAK
    from docx.shared import Inches

    d = Document()
    with open_pdf(src) as doc:
        for pno, page in enumerate(doc):
            if pno:
                d.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            items = []
            for b in page.get_text("dict")["blocks"]:
                y = b["bbox"][1]
                if b.get("type") == 0:
                    lines = []
                    size = 11.0
                    bold = False
                    for ln in b["lines"]:
                        spans = ln["spans"]
                        if spans:
                            size = max(size, max(s["size"] for s in spans)) if not lines else size
                            bold = bold or any("Bold" in s["font"] for s in spans)
                        lines.append("".join(s["text"] for s in spans))
                    txt = " ".join(l.strip() for l in lines).strip()
                    if txt:
                        items.append((y, "text", (txt, size, bold)))
                elif b.get("type") == 1 and b.get("image"):
                    items.append((y, "img", (b["image"], b["bbox"])))
            items.sort(key=lambda t: t[0])
            for _, kind, data in items:
                if kind == "text":
                    txt, size, bold = data
                    if size >= 16:
                        d.add_heading(txt, level=1 if size >= 20 else 2)
                    else:
                        p = d.add_paragraph()
                        r = p.add_run(txt)
                        r.bold = bold and len(txt) < 120
                else:
                    raw, bbox = data
                    width_in = min(6.5, max(0.5, (bbox[2] - bbox[0]) / 72))
                    try:
                        d.add_picture(io.BytesIO(raw), width=Inches(width_in))
                    except Exception:
                        pass
    out = sibling(src, ext=".docx")
    d.save(out)
    return [out]


# ---------------------------------------------------------------- DOCX
def _docx_paragraph_html(p) -> str:
    parts = []
    for r in p.runs:
        t = html.escape(r.text)
        if not t:
            continue
        if r.bold:
            t = f"<b>{t}</b>"
        if r.italic:
            t = f"<i>{t}</i>"
        if r.underline:
            t = f"<u>{t}</u>"
        parts.append(t)
    body = "".join(parts) or "&nbsp;"
    style = (p.style.name or "").lower() if p.style is not None else ""
    if style.startswith("heading"):
        lvl = "".join(c for c in style if c.isdigit()) or "1"
        lvl = str(min(int(lvl), 6))
        return f"<h{lvl}>{body}</h{lvl}>"
    if style == "title":
        return f"<h1>{body}</h1>"
    if "list" in style:
        return f"<p>&bull; {body}</p>"
    return f"<p>{body}</p>"


def docx_to_html(src: str | Path) -> str:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    d = Document(src)
    out = []
    for child in d.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            out.append(_docx_paragraph_html(Paragraph(child, d)))
        elif tag == "tbl":
            t = Table(child, d)
            rows = []
            for row in t.rows:
                cells = "".join(f"<td>{html.escape(c.text)}</td>" for c in row.cells)
                rows.append(f"<tr>{cells}</tr>")
            out.append("<table>" + "".join(rows) + "</table>")
    return "\n".join(out)


def docx_to_txt(src: str | Path) -> list[Path]:
    from docx import Document
    d = Document(src)
    lines = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            lines.append("\t".join(c.text for c in row.cells))
    out = sibling(src, ext=".txt")
    out.write_text("\n".join(lines), encoding="utf-8")
    return [out]


def _word_to_pdf(src: Path, out: Path) -> bool:
    """Use Microsoft Word (if installed) for a perfect-fidelity export."""
    if sys.platform != "win32" or os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        return False
    try:
        import win32com.client  # type: ignore
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        try:
            doc = word.Documents.Open(str(src.resolve()), ReadOnly=True)
            doc.SaveAs(str(out.resolve()), FileFormat=17)  # wdFormatPDF
            doc.Close(False)
        finally:
            word.Quit()
        return out.exists()
    except Exception:
        return False


CSS = """
* { font-family: sans-serif; }
body { font-size: 11pt; line-height: 1.35; }
h1 { font-size: 20pt; } h2 { font-size: 16pt; } h3 { font-size: 13pt; }
p { margin: 0 0 6pt 0; }
pre { font-family: monospace; font-size: 9.5pt; white-space: pre-wrap; }
table { border-collapse: collapse; margin: 6pt 0; }
td { border: 1px solid #888; padding: 3pt 5pt; font-size: 10pt; }
"""


def html_to_pdf(body_html: str, out: Path) -> None:
    story = fitz.Story(html=body_html, user_css=CSS)
    writer = fitz.DocumentWriter(str(out))
    mediabox = fitz.paper_rect("letter")
    where = mediabox + (54, 54, -54, -54)
    more = True
    while more:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()


def docx_to_pdf(src: str | Path) -> list[Path]:
    src = Path(src)
    out = sibling(src, ext=".pdf")
    if not _word_to_pdf(src, out):
        html_to_pdf(docx_to_html(src), out)
    return [out]


# ---------------------------------------------------------------- text
def read_text(src: str | Path) -> str:
    raw = Path(src).read_bytes()
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def text_to_pdf(src: str | Path) -> list[Path]:
    out = sibling(src, ext=".pdf")
    html_to_pdf(f"<pre>{html.escape(read_text(src))}</pre>", out)
    return [out]


def text_to_docx(src: str | Path) -> list[Path]:
    from docx import Document
    d = Document()
    for line in read_text(src).splitlines():
        d.add_paragraph(line)
    out = sibling(src, ext=".docx")
    d.save(out)
    return [out]



# ---------------------------------------------------------------- spreadsheets
SHEET_CSS = """
* { font-family: sans-serif; }
body { font-size: 9pt; line-height: 1.3; }
h2 { font-size: 14pt; color: #1e3a8a; margin-bottom: 8pt; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0; }
th { background-color: #2563eb; color: #ffffff; padding: 4pt 6pt; border: 1px solid #1d4ed8; text-align: left; font-size: 8.5pt; font-weight: bold; }
td { border: 1px solid #cbd5e1; padding: 3pt 5pt; font-size: 8.5pt; }
tr:nth-child(even) { background-color: #f8fafc; }
"""


def _excel_to_pdf(src: Path, out: Path) -> bool:
    """Use Microsoft Excel COM (if installed on Windows) for exact print fidelity."""
    if sys.platform != "win32":
        return False
    try:
        import win32com.client  # type: ignore
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        try:
            wb = excel.Workbooks.Open(str(src.resolve()), ReadOnly=True)
            wb.ExportAsFixedFormat(0, str(out.resolve()))  # 0 = xlTypePDF
            wb.Close(False)
        finally:
            excel.Quit()
        return out.exists()
    except Exception:
        return False


def read_sheet_rows(src: str | Path, max_rows: int = 5000) -> list[list[str]]:
    src = Path(src)
    ext = src.suffix.lower()
    rows: list[list[str]] = []
    if ext in (".xlsx", ".xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
        sheet = wb.active
        for i, row in enumerate(sheet.iter_rows(values_only=True)):
            if i >= max_rows:
                break
            row_vals = ["" if v is None else str(v).strip() for v in row]
            if any(row_vals):
                rows.append(row_vals)
        wb.close()
    elif ext == ".csv":
        import csv
        raw = src.read_bytes()
        encoding = "utf-8"
        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                raw.decode(enc)
                encoding = enc
                break
            except UnicodeDecodeError:
                continue
        text = raw.decode(encoding, "replace")
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample)
            delim = dialect.delimiter
        except Exception:
            delim = ";" if ";" in sample and "," not in sample else ","
        reader = csv.reader(text.splitlines(), delimiter=delim)
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            if any(c.strip() for c in row):
                rows.append([c.strip() for c in row])
    elif ext == ".xls":
        # If openpyxl or xlrd is not present, fall back to COM or empty
        pass
    return rows


def sheet_to_pdf(src: str | Path) -> list[Path]:
    src = Path(src)
    out = sibling(src, ext=".pdf")
    if not _excel_to_pdf(src, out):
        rows = read_sheet_rows(src)
        if not rows:
            raise UserError("A planilha está vazia ou não pôde ser lida.")
        html_rows = []
        for i, r in enumerate(rows):
            tag = "th" if i == 0 else "td"
            cells = "".join(f"<{tag}>{html.escape(c)}</{tag}>" for c in r)
            html_rows.append(f"<tr>{cells}</tr>")
        table_html = f"<h2>{html.escape(src.stem)}</h2><table>{''.join(html_rows)}</table>"
        story = fitz.Story(html=table_html, user_css=SHEET_CSS)
        writer = fitz.DocumentWriter(str(out))
        num_cols = max(len(r) for r in rows) if rows else 1
        mediabox = fitz.paper_rect("letter-l") if num_cols > 4 else fitz.paper_rect("letter")
        where = mediabox + (36, 36, -36, -36)
        more = True
        while more:
            dev = writer.begin_page(mediabox)
            more, _ = story.place(where)
            story.draw(dev)
            writer.end_page()
        writer.close()
    return [out]


def sheet_to_csv(src: str | Path) -> list[Path]:
    import csv
    src = Path(src)
    rows = read_sheet_rows(src)
    if not rows:
        raise UserError("A planilha está vazia.")
    out = sibling(src, ext=".csv")
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerows(rows)
    return [out]


def csv_to_xlsx(src: str | Path) -> list[Path]:
    src = Path(src)
    rows = read_sheet_rows(src)
    if not rows:
        raise UserError("O arquivo CSV está vazio.")
    out = sibling(src, ext=".xlsx")
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = src.stem[:31]

    header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Segoe UI", size=10)
    border_side = Side(border_style="thin", color="CBD5E1")
    cell_border = Border(left=border_side, right=border_side, top=border_side, bottom=border_side)

    for row_idx, row in enumerate(rows, start=1):
        for col_idx, val in enumerate(row, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.border = cell_border
            if row_idx == 1:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.font = data_font

    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = max(12, min(50, max_len + 3))

    wb.save(out)
    wb.close()
    return [out]


def sheet_to_json(src: str | Path) -> list[Path]:
    import json
    src = Path(src)
    rows = read_sheet_rows(src)
    if not rows:
        raise UserError("O arquivo está vazio.")
    headers = rows[0]
    data = []
    for r in rows[1:]:
        row_dict = {headers[i] if i < len(headers) and headers[i] else f"col_{i+1}": (r[i] if i < len(r) else "") for i in range(len(r))}
        data.append(row_dict)
    out = sibling(src, ext=".json")
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return [out]


def sheet_to_html(src: str | Path) -> list[Path]:
    src = Path(src)
    rows = read_sheet_rows(src)
    if not rows:
        raise UserError("O arquivo está vazio.")
    out = sibling(src, ext=".html")
    html_rows = []
    for i, r in enumerate(rows):
        tag = "th" if i == 0 else "td"
        cells = "".join(f"<{tag}>{html.escape(c)}</{tag}>" for c in r)
        html_rows.append(f"<tr>{cells}</tr>")

    content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>{html.escape(src.stem)}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 24px; background: #f8fafc; color: #1e293b; }}
h2 {{ font-size: 20px; margin-bottom: 16px; color: #0f172a; }}
.card {{ background: white; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.08); overflow: hidden; border: 1px solid #e2e8f0; }}
table {{ border-collapse: collapse; width: 100%; text-align: left; font-size: 13px; }}
th {{ background: #2563eb; color: white; padding: 10px 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em; }}
td {{ padding: 10px 14px; border-bottom: 1px solid #e2e8f0; }}
tr:nth-child(even) {{ background: #f8fafc; }}
tr:hover {{ background: #eff6ff; }}
</style>
</head>
<body>
<h2>{html.escape(src.stem)}</h2>
<div class="card">
<table>
{''.join(html_rows)}
</table>
</div>
</body>
</html>
"""
    out.write_text(content, encoding="utf-8")
    return [out]


def sheet_to(src: str | Path, target: str) -> list[Path]:
    target = target.upper()
    if target == "PDF":
        return sheet_to_pdf(src)
    if target == "CSV":
        return sheet_to_csv(src)
    if target == "XLSX":
        return csv_to_xlsx(src)
    if target == "JSON":
        return sheet_to_json(src)
    if target == "HTML":
        return sheet_to_html(src)
    raise ValueError(f"Can't convert spreadsheet to {target}")


def extract_office_media(src: str | Path) -> list[Path]:
    """Extracts all embedded images and media from .docx, .pptx, .xlsx, .xlsm files."""
    import zipfile
    from .util import unique_path
    p = Path(src)
    out_dir = unique_path(p.parent / f"{p.stem}_midias")
    out_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    MEDIA_EXTS = {".png", ".jpg", ".jpeg", ".svg", ".gif", ".emf", ".wmf", ".tiff", ".webp"}
    try:
        with zipfile.ZipFile(p, "r") as zf:
            for name in zf.namelist():
                lower_name = name.lower()
                if "media/" in lower_name and any(lower_name.endswith(ext) for ext in MEDIA_EXTS):
                    file_bytes = zf.read(name)
                    base_name = Path(name).name
                    dest_file = unique_path(out_dir / base_name)
                    dest_file.write_bytes(file_bytes)
                    extracted.append(dest_file)
    except Exception as e:
        raise ValueError(f"Nao foi possivel extrair midias de {p.name}: {e}")
    if not extracted:
        raise ValueError(f"Nenhuma midia ou imagem encontrada dentro de {p.name}")
    return extracted

# ---------------------------------------------------------------- dispatch
def targets_for(cat: str, src_ext: str, num_files: int = 1) -> list[str]:
    src_ext = src_ext.lower().lstrip(".")
    same = {"jpeg": "JPG", "jpg": "JPG", "tif": "TIFF", "tiff": "TIFF", "heif": "HEIC"}
    cur = same.get(src_ext, src_ext.upper())
    if cat == "image":
        t = [x for x in IMAGE_TARGETS if x != cur]
        if not HEIF_OK:
            t = [x for x in t if x != "HEIC"]
        if num_files > 1:
            out = []
            for item in t:
                if item == "PDF":
                    out.extend(["PDF (1 doc)", "PDF (sep)"])
                else:
                    out.append(item)
            return out
        return t
    if cat == "sheet":
        if src_ext in ("xlsx", "xls", "xlsm", "xlsb"):
            return ["PDF", "CSV", "JSON", "HTML", "Extrair Midias"]
        if src_ext == "csv":
            return ["XLSX", "PDF", "JSON", "HTML"]
        return ["PDF", "CSV", "JSON"]
    if cat == "data":
        cur_fmt = src_ext.upper()
        if cur_fmt in ("YML", "YAML"):
            cur_fmt = "YAML"
        return [t for t in DATA_TARGETS if t.upper() != cur_fmt]
    if cat == "docx":
        return ["PDF", "TXT", "Extrair Midias"]
    if cat == "archive":
        return ["Extrair", "Zip", "Zip (Max)"]
    if cat in ("generic", "directory"):
        return ["Zip", "Zip (Max)"]
    return {"pdf": PDF_TARGETS, "docx": ["PDF", "TXT", "Extrair Midias"], "text": TEXT_TARGETS}.get(cat, ["Zip", "Zip (Max)"])



def _raw_convert(src: str | Path, cat: str, target: str) -> list[Path]:
    target = target.upper()
    if cat == "image":
        if target in ("PDF (SEP)", "PDF"):
            return image_to(src, "PDF")
        return image_to(src, target)
    if cat == "sheet":
        return sheet_to(src, target)
    if cat == "pdf":
        if target in ("JPG", "PNG"):
            return pdf_to_images(src, target)
        if target == "TXT":
            return pdf_to_txt(src)
        if target == "DOCX":
            return pdf_to_docx(src)
    if cat == "docx":
        return docx_to_pdf(src) if target == "PDF" else docx_to_txt(src)
    if cat == "data":
        from .data_convert import convert_data
        return convert_data(src, target)
    if cat == "text":
        return text_to_pdf(src) if target == "PDF" else text_to_docx(src)
    if "EXTRAIR" in target and ("MIDIA" in target or "MÍDIA" in target):
        return extract_office_media(src)
    if target in ("EXTRAIR", "EXTRACT"):
        return extract_archive(src)
    if "ZIP" in target:
        level = 9 if "MAX" in target else 6
        return zip_files([src], compress_level=level)
    raise ValueError(f"Can't convert {cat} to {target}")


def zip_files(paths: list[str | Path], compress_level: int = 6) -> list[Path]:
    import zipfile
    from .util import unique_path
    paths = [Path(p) for p in paths]
    p0 = paths[0]
    out_name = f"{p0.stem}.zip" if len(paths) == 1 else "Arquivos.zip"
    out_zip = unique_path(p0.parent / out_name)
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=compress_level) as zf:
        for p in paths:
            if p.is_dir():
                for root, _, files in os.walk(p):
                    for file in files:
                        full_path = Path(root) / file
                        rel_path = full_path.relative_to(p.parent)
                        zf.write(full_path, arcname=str(rel_path))
            elif p.is_file():
                zf.write(p, arcname=p.name)
    return [out_zip]


def extract_archive(src: str | Path) -> list[Path]:
    import zipfile
    from .util import unique_path
    z = Path(src)
    out_dir = unique_path(z.parent / z.stem)
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(z, "r") as zf:
        zf.extractall(out_dir)
        names = zf.namelist()
    return [out_dir / n for n in names[:5]] or [out_dir]



def convert(src: str | Path, cat: str, target: str) -> list[Path]:
    outs = _raw_convert(src, cat, target)
    # Record history
    try:
        from .history import record_conversion
        record_conversion(src, outs, cat)
    except Exception:
        pass

    # Safe recycle bin / only if smaller checks if configured
    try:
        from .settings import Settings
        s = Settings()
        if s.get("only_if_smaller") and outs:
            from .safe_trash import verify_only_if_smaller
            outs = verify_only_if_smaller(src, outs)
        if s.get("replace_original") and outs:
            from .safe_trash import move_to_trash
            move_to_trash(src)
    except Exception:
        pass

    return outs

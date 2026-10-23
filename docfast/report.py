"""Turns 'what just happened' into a short, useful summary for the notification:
sizes saved, new dimensions, pages, fields removed…"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .util import category, file_size, human_size
from .i18n import get_language, t


@dataclass
class Result:
    title: str
    detail: str
    outs: list[Path]
    srcs: list[Path] = field(default_factory=list)
    good: str = ""     # highlighted figure, e.g. "−75%"

    @property
    def thumb(self) -> Path | None:
        for o in self.outs:
            if category(o) == "image":
                return o
        return None


def dims(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return None


def pages(path: Path) -> int | None:
    try:
        from .convert import fitz
        with fitz.open(path) as d:
            return d.page_count
    except Exception:
        return None


def size_change(before: int, after: int) -> tuple[str, str]:
    """('2.4 MB → 610 KB', '75% menor' / '75% smaller')"""
    text = f"{human_size(before)} → {human_size(after)}"
    if before <= 0:
        return text, ""
    pct = (1 - after / before) * 100
    is_pt = (get_language() == "pt_BR")
    if pct >= 1:
        return text, f"{pct:.0f}% {t('toast_smaller')}"
    if pct <= -1:
        return text, f"{-pct:.0f}% {t('toast_larger')}"
    return text, t("toast_same_size")


def _dim_str(d) -> str:
    return f"{d[0]}×{d[1]}" if d else ""


def summarize(action: str, srcs: list, outs: list, extra: str = "") -> Result:
    srcs = [Path(s) for s in srcs]
    outs = [Path(o) for o in outs if o]
    is_pt = (get_language() == "pt_BR")
    if not outs:
        msg = "Nenhum arquivo gravado" if is_pt else "Nothing was written"
        return Result(action, extra or msg, [], srcs)
    src = srcs[0] if srcs else outs[0]
    before = sum(file_size(s) for s in srcs if s.is_file())
    after = sum(file_size(o) for o in outs if o.is_file())
    kind, _, name = action.partition(":")
    o0 = outs[0]
    good = ""

    if kind == "convert":
        fmt = name
        if fmt == "PDF (1 doc)":
            title = f"{len(srcs)} imagens → 1 PDF" if is_pt else f"{len(srcs)} images → 1 PDF"
        elif fmt == "PDF (sep)":
            title = f"{len(outs)} imagens → {len(outs)} PDFs individuais" if is_pt else f"{len(outs)} images → {len(outs)} individual PDFs"
        elif len(srcs) > 1 and len(outs) == 1:
            title = f"{len(srcs)} arquivos → 1 {fmt}" if is_pt else f"{len(srcs)} files → 1 {fmt}"
        elif len(outs) > 1 and len(srcs) == 1:
            n = pages(src)
            title = f"{n or len(outs)} páginas → {len(outs)} {fmt}s" if is_pt else f"{n or len(outs)} pages → {len(outs)} {fmt}s"
        elif len(outs) > 1:
            title = f"{len(outs)} arquivos → {fmt}" if is_pt else f"{len(outs)} files → {fmt}"
        else:
            title = f"{src.suffix.lstrip('.').upper()} → {fmt}"
        bits = [o0.name if len(outs) == 1 else f"{o0.parent.name}/{o0.name} …"]
        d = dims(o0) if category(o0) == "image" else None
        if d:
            bits.append(_dim_str(d))
        if o0.suffix.lower() == ".pdf":
            n = pages(o0)
            if n:
                p_word = ("página" if n == 1 else "páginas") if is_pt else ("page" if n == 1 else "pages")
                bits.append(f"{n} {p_word}")
        bits.append(human_size(after))
        return Result(title, " · ".join(bits), outs, srcs)

    if name == "Compress":
        sizes, verdict = size_change(before, after)
        if is_pt:
            title = f"Comprimidos {len(srcs)} arquivos" if len(srcs) > 1 else "Comprimido"
            if verdict.endswith(t("toast_larger")) or verdict == t("toast_same_size"):
                verdict = t("toast_already_compressed")
        else:
            title = f"Compressed {len(srcs)} files" if len(srcs) > 1 else "Compressed"
            if verdict.endswith("larger") or verdict == "same size":
                verdict = "already well compressed"
        return Result(title, sizes + (f" · {extra}" if extra else ""), outs, srcs, good=verdict)

    if name in ("Crop", "Resize", "Edit"):
        d0, d1 = dims(src), dims(o0)
        verb = ({"Crop": "Recortado", "Resize": "Redimensionado", "Edit": "Editado"} if is_pt
                else {"Crop": "Cropped", "Resize": "Resized", "Edit": "Edited"})[name]
        if len(outs) > 1:
            imgs_word = "imagens" if is_pt else "images"
            return Result(f"{verb} {len(outs)} {imgs_word}", f"{human_size(before)} → {human_size(after)}", outs, srcs)
        detail = f"{_dim_str(d0)} → {_dim_str(d1)}" if d0 and d1 and d0 != d1 else _dim_str(d1)
        if extra:
            detail += f" · {extra}"
        return Result(verb, f"{detail} · {o0.name}", outs, srcs)

    if name == "Add BG":
        title = "Fundo adicionado" if is_pt else "Background added"
        return Result(title, f"{_dim_str(dims(o0))} PNG · {human_size(after)} · {o0.name}", outs, srcs)

    if name == "Annotate":
        title = "Anotado" if is_pt else "Annotated"
        return Result(title, f"{extra} · {o0.name}" if extra else o0.name, outs, srcs)

    if name == "Redact":
        title = "Tarjado" if is_pt else "Redacted"
        good = t("toast_burned_pixels") if is_pt else "burned into pixels"
        return Result(title, f"{extra} · {o0.name}" if extra else o0.name, outs, srcs, good=good)

    if name == "Metadata":
        title = "Metadados removidos" if is_pt else "Metadata removed"
        good = t("toast_private_copy") if is_pt else "private copy"
        return Result(title, f"{extra} · {o0.name}" if extra else o0.name, outs, srcs, good=good)

    if name == "Split":
        title = f"Dividido em {len(outs)} PDFs" if is_pt else f"Split into {len(outs)} PDFs"
        return Result(title, f"{o0.name} …", outs, srcs)

    if name == "Merge":
        n = pages(o0)
        p_word = "páginas" if is_pt else "pages"
        title = f"Mesclados {len(srcs)} PDFs" if is_pt else f"Merged {len(srcs)} PDFs"
        return Result(title, f"{n} {p_word} · {human_size(after)} · {o0.name}", outs, srcs)

    if name == "Rotate":
        n = pages(o0)
        p_word = ("página" if n == 1 else "páginas") if is_pt else ("page" if n == 1 else "pages")
        title = "Girado 90°" if is_pt else "Rotated 90°"
        return Result(title, f"{n} {p_word} · {o0.name}", outs, srcs)

    if name == "Protect":
        title = "Protegido por senha" if is_pt else "Password protected"
        good = t("toast_encrypted") if is_pt else "encrypted"
        return Result(title, f"AES-256 · {o0.name}", outs, srcs, good=good)

    if name == "Extract":
        if is_pt:
            title = "Extraída 1 imagem" if len(outs) == 1 else f"Extraídas {len(outs)} imagens"
        else:
            title = f"Extracted {len(outs)} image{'s' if len(outs) != 1 else ''}"
        return Result(title, f"{o0.parent.name}/ · {human_size(after)}", outs, srcs)

    # generic
    return Result(name or action, f"{o0.name} · {human_size(after)}", outs, srcs)

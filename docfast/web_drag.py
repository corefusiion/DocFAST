"""Web Drag & Drop Downloader for DocFAST.
Detects when a user drags an image, a web URL, or an HTML image element directly
from Chrome, Edge, Firefox, or Safari, downloads the payload to a local cache,
and returns the local file path so the radial conversion menu works seamlessly.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import sys
import tempfile
import urllib.parse
import urllib.request

from PySide6.QtCore import QMimeData


def _web_cache_dir() -> Path:
    d = Path(tempfile.gettempdir()) / "DocFAST_WebDrag"
    d.mkdir(parents=True, exist_ok=True)
    return d


def extract_web_drag_file(mime_data: QMimeData) -> Path | None:
    """Inspects QMimeData from a drop event. If it comes from a web browser,
    downloads the image/file and returns the local Path. Otherwise returns None.
    """
    # 1. Check for direct local files first (if present, not a pure web drag)
    if mime_data.hasUrls():
        for url in mime_data.urls():
            if url.isLocalFile():
                return Path(url.toLocalFile())

    target_url: str | None = None

    # 2. Check HTML format for <img src="...">
    if mime_data.hasHtml():
        html = mime_data.html()
        match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if match:
            target_url = match.group(1)

    # 3. Check plain text for http/https URL ending with media/doc extension
    if not target_url and mime_data.hasText():
        txt = mime_data.text().strip()
        if txt.startswith(("http://", "https://")):
            target_url = txt

    # 4. Check url list for remote http/https
    if not target_url and mime_data.hasUrls():
        for url in mime_data.urls():
            s = url.toString()
            if s.startswith(("http://", "https://")):
                target_url = s
                break

    if not target_url:
        return None

    # Handle data: URLs (base64 image payload)
    if target_url.startswith("data:image/"):
        try:
            import base64
            header, b64_data = target_url.split(",", 1)
            ext = ".png"
            if "jpeg" in header or "jpg" in header:
                ext = ".jpg"
            elif "webp" in header:
                ext = ".webp"
            out_file = _web_cache_dir() / f"web_image_{os.getpid()}_{int(tempfile.time.time()*1000)}{ext}"
            out_file.write_bytes(base64.b64decode(b64_data))
            return out_file
        except Exception:
            return None

    # Download remote file
    try:
        parsed = urllib.parse.urlparse(target_url)
        path_name = Path(parsed.path).name or "imagem.png"
        if "." not in path_name:
            path_name += ".png"

        clean_name = re.sub(r'[^a-zA-Z0-9_\.-]', '_', path_name)
        dest = _web_cache_dir() / clean_name

        req = urllib.request.Request(
            target_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
            if data:
                dest.write_bytes(data)
                return dest
    except Exception:
        pass

    return None

"""Extract text for cite-only get_document responses."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional, Tuple


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def extract_text(filename: str, data: bytes) -> Tuple[Optional[str], str]:
    """
    Return (text_or_none, extraction_method).
    Prefers DecisionPen FileProcessor when that package is importable in-process;
    otherwise returns text only for plain UTF-8 text/markdown.
    """
    lower = filename.lower()
    if lower.endswith((".txt", ".md", ".markdown")):
        try:
            return data.decode("utf-8"), "utf8"
        except UnicodeDecodeError:
            return data.decode("utf-8", errors="replace"), "utf8_replace"

    try:
        from src.file_processor import FileProcessor
    except ImportError:
        return None, "unavailable_no_fileprocessor"

    class _BytesFile:
        def __init__(self, name: str, content: bytes):
            self.filename = name
            self._content = content

        async def read(self):
            return self._content

    try:
        processed = await FileProcessor.process_file(_BytesFile(filename, data))
        text = (processed.get("content") or "").strip()
        return (text or None), "file_processor"
    except Exception as e:
        return None, f"file_processor_error:{e}"


def build_document_envelope(
    *,
    item_id: str,
    uri: str,
    mode: str,
    size: int,
    digest: str,
    mime_type: Optional[str],
    last_modified: Optional[str],
    text: Optional[str],
    extraction_method: str,
    max_text_chars: int,
    binary_base64: Optional[str] = None,
) -> Dict[str, Any]:
    truncated = False
    body = text
    if body is not None and len(body) > max_text_chars:
        body = body[:max_text_chars]
        truncated = True

    env: Dict[str, Any] = {
        "source_system": "s3",
        "uri": uri,
        "item_id": item_id,
        "title": item_id.rsplit("/", 1)[-1],
        "mime_type": mime_type,
        "bytes_sha256": digest,
        "size": size,
        "last_modified": last_modified,
        "mode": mode,
        "text": body,
        "text_truncated": truncated,
        "extraction_method": extraction_method,
        "persisted": False,
    }
    if binary_base64 is not None:
        env["content_base64"] = binary_base64
    return env

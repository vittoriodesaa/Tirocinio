"""
Acquisizione del documento: riceve il file caricato e lo rende disponibile per la pipeline.
"""
from __future__ import annotations

import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path

from typing import Optional, Tuple

from pipeline.core.agent_logging import narrative, phase_percent_for
from pipeline.models.schemas import AcquisitionRecord, SourceInput

_OCR_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
_TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".rst", ".csv"}


class AcquisitionAgent:
    """Registra upload utente nel workspace e produce SourceInput."""

    def __init__(self, workspace_dir: str):
        self.workspace = Path(workspace_dir).resolve()
        self.uploads_dir = self.workspace / "uploads"
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        pass

    def _guess_media_type(self, filename: str) -> str:
        mt, _ = mimetypes.guess_type(filename)
        return mt or "application/octet-stream"

    def _needs_ocr(self, ext: str, media_type: str) -> bool:
        if "image" in media_type:
            return True
        return ext in {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}

    def _sanitize_source_id(self, source_id: str) -> str:
        sid = re.sub(r"[^a-zA-Z0-9_-]", "_", source_id.strip())[:64]
        return sid or "doc_sconosciuto"

    def acquisisci_file(
        self,
        file_bytes: bytes,
        filename: str,
        source_id: str,
        *,
        language_hint: str = "it",
        domain_hint: Optional[str] = None,
    ) -> Tuple[AcquisitionRecord, SourceInput]:
        sid = self._sanitize_source_id(source_id)
        ext = Path(filename).suffix.lower() or ".bin"
        safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", Path(filename).name)
        dest = self.uploads_dir / f"{sid}{ext}"

        dest.write_bytes(file_bytes)
        media_type = self._guess_media_type(filename)
        ocr = self._needs_ocr(ext, media_type)

        record = AcquisitionRecord(
            source_id=sid,
            filename=safe_name,
            media_type=media_type,
            storage_ref=str(dest),
            size_bytes=len(file_bytes),
            estensione=ext,
            ocr_probabile=ocr,
            acquisito_il=datetime.now(timezone.utc).isoformat(),
        )

        hint = ext.lstrip(".") or "unknown"
        if ext in (".pdf",):
            hint = "application/pdf"
        elif ext in (".doc", ".docx"):
            hint = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        source = SourceInput(
            source_id=sid,
            filename=safe_name,
            media_type=media_type,
            source_type_hint=hint,
            storage_ref=str(dest),
            language_hint=language_hint,
            domain_hint=domain_hint,
            ocr_required=ocr,
            title_hint=Path(filename).stem,
        )

        meta_path = self.uploads_dir / f"{sid}_acquisition.json"
        meta_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")

        narrative(
            f"Ho salvato il file «{safe_name}» ({len(file_bytes) // 1024} KB) nella cartella del corso.",
            percent=phase_percent_for("acquisition", 1.0),
        )
        return record, source

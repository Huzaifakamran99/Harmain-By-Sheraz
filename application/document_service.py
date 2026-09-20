"""
Passport/visa document upload + OCR review workflow (SRS 4.4, 16.8).
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from core.config import get_documents_storage_dir
from core.exceptions import ValidationError, DocumentProcessingError
from core.logging_setup import get_logger
from infrastructure.ocr_service import (
    extract_passport_data, OcrResult, reader_diagnostics, reader_problems, missing_component_hint,
)

logger = get_logger(__name__)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".webp", ".tif", ".tiff",
                       ".bmp", ".heic", ".heif"}
MAX_FILE_SIZE_MB = 15


class DocumentService:
    def validate_file(self, file_path: Path) -> None:
        if not file_path.exists():
            raise ValidationError("Selected file could not be found.")
        if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"Unsupported file type '{file_path.suffix}'. Allowed: "
                f"{', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            raise ValidationError(f"File is too large ({size_mb:.1f} MB). Maximum is {MAX_FILE_SIZE_MB} MB.")

    def store_document(self, source_path: Path) -> Path:
        """Copies the uploaded document into secure app storage under a random name."""
        self.validate_file(source_path)
        dest_dir = get_documents_storage_dir()
        dest_name = f"{uuid.uuid4().hex}{source_path.suffix.lower()}"
        dest_path = dest_dir / dest_name
        try:
            shutil.copy2(source_path, dest_path)
        except OSError as e:
            logger.error("Failed to store document: %s", e)
            raise ValidationError("Could not save the uploaded document. Please try again.") from e
        return dest_path

    def run_ocr(self, stored_path: Path) -> OcrResult:
        """
        Read a stored passport/visa. Never blocks saving: a failure here
        returns a result with a warning, and the administrator types the
        details in by hand (FR-OCR-05/06/08).
        """
        try:
            return extract_passport_data(stored_path)
        except DocumentProcessingError:
            raise

    def reading_capabilities(self) -> dict:
        """What this computer can currently read - shown in Settings."""
        return reader_diagnostics()

    def reading_problems(self) -> dict:
        """Exact reason each missing reader component is missing."""
        return reader_problems()

    def setup_hint(self) -> str:
        """Empty string when nothing else needs installing."""
        return missing_component_hint()

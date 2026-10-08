from __future__ import annotations

import hashlib
import mimetypes
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings


@dataclass(slots=True)
class SavedUpload:
    document_id: uuid.UUID
    original_filename: str
    stored_filename: str
    media_type: str
    source_path: str
    sha256: str


class FileManager:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.root = self.settings.storage_root
        self.root.mkdir(parents=True, exist_ok=True)

    def document_dir(self, document_id: uuid.UUID) -> Path:
        path = self.root / str(document_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def page_image_path(self, document_id: uuid.UUID, page_number: int, suffix: str = ".png") -> Path:
        return self.document_dir(document_id) / f"page-{page_number:04d}{suffix}"

    def snapshot_dir(self, document_id: uuid.UUID) -> Path:
        path = self.document_dir(document_id) / "snapshots"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def artifact_dir(self, document_id: uuid.UUID) -> Path:
        path = self.document_dir(document_id) / "artifacts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def snapshot_path(self, document_id: uuid.UUID, original_filename: str) -> Path:
        return self.snapshot_dir(document_id) / original_filename

    def artifact_revision_path(self, document_id: uuid.UUID, revision: int, original_filename: str) -> Path:
        path = self.artifact_dir(document_id) / f"v{revision:04d}"
        path.mkdir(parents=True, exist_ok=True)
        return path / original_filename

    def attachment_path(self, document_id: uuid.UUID, attachment_name: str) -> Path:
        safe_name = attachment_name.replace("/", "_").replace("\\", "_")
        attachments_dir = self.document_dir(document_id) / "attachments"
        attachments_dir.mkdir(parents=True, exist_ok=True)
        return attachments_dir / safe_name

    def _is_allowed_media_type(self, media_type: str, original_filename: str) -> bool:
        if media_type in self.settings.allowed_media_types:
            return True
        suffix = Path(original_filename).suffix.lower()
        allowed_suffixes = {
            ".pdf",
            ".png",
            ".jpg",
            ".jpeg",
            ".tif",
            ".tiff",
            ".webp",
            ".bmp",
            ".docx",
            ".xlsx",
            ".pptx",
            ".txt",
            ".eml",
        }
        return suffix in allowed_suffixes

    async def save_upload(self, upload: UploadFile, document_id: uuid.UUID) -> SavedUpload:
        original_filename = upload.filename or f"{document_id}.bin"
        suffix = Path(original_filename).suffix
        stored_filename = f"{uuid.uuid4().hex}{suffix}"
        media_type = upload.content_type or mimetypes.guess_type(original_filename)[0] or "application/octet-stream"

        # Validate media type
        allowed = self.settings.allowed_media_types
        if not self._is_allowed_media_type(media_type, original_filename):
            raise ValueError(
                f"Type de fichier non autorise: {media_type}. "
                f"Types acceptes: {', '.join(allowed)}"
            )

        target_path = self.document_dir(document_id) / stored_filename
        max_bytes = self.settings.max_upload_size_mb * 1024 * 1024

        # Stream chunks to disk with size check
        hasher = hashlib.sha256()
        total = 0
        try:
            with target_path.open("wb") as f:
                while True:
                    chunk = await upload.read(256 * 1024)  # 256 KB
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError(
                            f"Le fichier depasse la limite de {self.settings.max_upload_size_mb} Mo."
                        )
                    hasher.update(chunk)
                    f.write(chunk)
        except Exception:
            target_path.unlink(missing_ok=True)
            raise

        return SavedUpload(
            document_id=document_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            media_type=media_type,
            source_path=str(target_path),
            sha256=hasher.hexdigest(),
        )

    def save_attachment(self, document_id: uuid.UUID, filename: str, content: bytes) -> Path:
        path = self.attachment_path(document_id, filename)
        path.write_bytes(content)
        return path

    def save_page_image(self, document_id: uuid.UUID, page_number: int, content: bytes, suffix: str = ".png") -> str:
        path = self.page_image_path(document_id, page_number, suffix=suffix)
        path.write_bytes(content)
        return str(path)

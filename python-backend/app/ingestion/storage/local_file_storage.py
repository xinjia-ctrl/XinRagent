from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi import UploadFile

from app.common.ids import generate_id
from app.core.config import settings


class StoredFile:
    def __init__(
        self,
        file_id: str,
        original_name: str,
        file_type: str,
        file_size: int,
        path: Path,
    ) -> None:
        self.file_id = file_id
        self.original_name = original_name
        self.file_type = file_type
        self.file_size = file_size
        self.path = path


class LocalFileStorage:
    def __init__(self, base_dir: str | Path | None = None) -> None:
        self.base_dir = Path(base_dir or settings.ingestion_storage_dir)

    async def save_upload(self, kb_id: str, upload: UploadFile) -> StoredFile:
        file_id = generate_id()
        original_name = upload.filename or file_id
        suffix = Path(original_name).suffix.lower()
        target_dir = self.base_dir / kb_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{file_id}{suffix}"

        size = 0
        with target_path.open("wb") as file:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                file.write(chunk)

        return StoredFile(
            file_id=file_id,
            original_name=original_name,
            file_type=suffix.removeprefix("."),
            file_size=size,
            path=target_path,
        )

    def prepare_remote_source(self, kb_id: str, source_location: str, file_name: str | None = None) -> StoredFile:
        file_id = generate_id()
        original_name = file_name or self._file_name_from_url(source_location) or f"{file_id}.txt"
        suffix = Path(original_name).suffix.lower() or ".txt"
        if not Path(original_name).suffix:
            original_name = f"{original_name}{suffix}"
        target_dir = self.base_dir / kb_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{file_id}{suffix}"
        return StoredFile(
            file_id=file_id,
            original_name=original_name,
            file_type=suffix.removeprefix("."),
            file_size=0,
            path=target_path,
        )

    @staticmethod
    def _file_name_from_url(source_location: str) -> str | None:
        parsed_name = Path(unquote(urlparse(source_location).path)).name
        return parsed_name or None

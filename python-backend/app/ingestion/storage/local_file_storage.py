from pathlib import Path

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

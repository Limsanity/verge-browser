from datetime import datetime

from pydantic import BaseModel


class FileEntry(BaseModel):
    name: str
    path: str
    size: int
    is_dir: bool
    modified_at: datetime


class WriteFileRequest(BaseModel):
    path: str
    content: str
    overwrite: bool = False


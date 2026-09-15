"""Adapts FastAPI's UploadFile to what crud.py's photo-writing functions
expect: Streamlit's UploadedFile shape (a `.name` attribute and a
`.getbuffer()` method returning bytes). crud.add_cleanliness_audit,
add_lot_verification's photo path, etc. need no changes to accept photos
from either frontend - this is the only new code the swap requires.
"""
from fastapi import UploadFile


class _BufferedUpload:
    def __init__(self, filename: str, data: bytes):
        self.name = filename or "upload.jpg"
        self._data = data

    def getbuffer(self) -> bytes:
        return self._data


async def to_streamlit_like(upload: UploadFile) -> _BufferedUpload:
    return _BufferedUpload(upload.filename, await upload.read())


async def to_streamlit_like_many(uploads: list[UploadFile]) -> list[_BufferedUpload]:
    return [await to_streamlit_like(u) for u in uploads if u is not None and u.filename]

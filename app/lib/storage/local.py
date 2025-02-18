from asyncio import get_running_loop
from functools import lru_cache
from pathlib import Path
from typing import override

from app.config import FILE_STORE_DIR
from app.lib.buffered_random import buffered_randbytes
from app.lib.storage.base import StorageBase
from app.models.types import StorageKey


class LocalStorage(StorageBase):
    """Local file storage."""

    __slots__ = ('_base_dir',)

    def __init__(self, context: str):
        super().__init__(context)
        self._base_dir: Path = FILE_STORE_DIR.joinpath(context)

    @override
    async def load(self, key: StorageKey) -> bytes:
        path = _get_path(self._base_dir, key)
        loop = get_running_loop()
        return await loop.run_in_executor(None, path.read_bytes)

    @override
    async def save(self, data: bytes, suffix: str) -> StorageKey:
        key = self._make_key(suffix)
        path = _get_path(self._base_dir, key)
        path.parent.mkdir(parents=True, exist_ok=True)

        temp_name = f'.{buffered_randbytes(16).hex()}.tmp'
        temp_path = path.with_name(temp_name)

        with temp_path.open('xb') as f:
            loop = get_running_loop()
            await loop.run_in_executor(None, f.write, data)

        temp_path.rename(path)
        return key

    @override
    async def delete(self, key: StorageKey) -> None:
        path = _get_path(self._base_dir, key)
        path.unlink(missing_ok=True)


@lru_cache(maxsize=1024)
def _get_path(base_dir: Path, key: StorageKey) -> Path:
    """
    Get the path to a file in the storage by key string.

    >>> _get_path(Path('context'), 'file_key')
    Path('.../context/fi/le/file_key')
    """
    return base_dir.joinpath(key[:2], key[2:4], key)

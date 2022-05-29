__author__ = """Aria Bagheri"""
__email__ = 'ariab9342@gmail.com'
__version__ = '1.0.5'

import asyncio
import datetime
import math
import os
import pathlib
import shutil
from typing import Callable, Awaitable, Any

import aiofiles
import aiohttp as aiohttp
import requests

_HEADERS = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/1.0.5.94 Safari/537.36'
}


class _Progress:
    last_update_at: datetime.datetime = None
    value: int = 0

    def __init__(self):
        pass

    def update(self, v: int):
        self.value += v

    def should_update(self):
        if not self.last_update_at:
            self.last_update_at = datetime.datetime.now()
        if self.last_update_at + datetime.timedelta(milliseconds=200) >= datetime.datetime.now():
            return False
        self.last_update_at = datetime.datetime.now()
        return True


class Axel:
    block_size = 5368709 * 2
    connections: int = 16
    progress_callback: Callable[[int, int], Awaitable[Any]] = None

    def __init__(self, block_size: int = 5368709 * 2, connections: int = 16,
                 progress_callback: Callable[[int, int], Awaitable[Any]] = None):
        self.block_size = block_size
        self.connections = connections
        self.progress_callback = progress_callback

    async def download_file(self, link: str, output: str):
        output_path = pathlib.Path(output)
        if output_path.is_dir():
            raise Exception("Output is not a file!")
        os.makedirs("temp/", exist_ok=True)
        async with aiohttp.ClientSession() as session:
            async with session.head(link) as download_head:
                accept_ranges = 'accept-ranges' in download_head.headers and 'bytes' in \
                                download_head.headers['accept-ranges']

                total_size = int(download_head.headers['content-length'])
                if not accept_ranges or self.connections == 1:
                    await self._download_file_slow(session, link, output, total_size)
                else:
                    await self._download_file_multithread(session, link, output_path, total_size)

    async def _download_file_slow(self, session: aiohttp.ClientSession, link: str, output: str, total_size: int):
        progress = _Progress()
        async with session.get(link, allow_redirects=True, chunked=True, timeout=None) as r:
            async with aiofiles.open(output, 'wb') as f:
                async for chunk, _ in r.content.iter_chunks():
                    await f.write(chunk)
                    progress.update(len(chunk))

                    if self.progress_callback:
                        await self.progress_callback(progress.value, total_size)

    async def _download_file_multithread(self, session: aiohttp.ClientSession, link: str,
                                         output: pathlib.Path, total_size: int):
        chunk_size = math.ceil(total_size / self.connections)
        progress = _Progress()

        async def download_chunk(chunk_index):
            chunk_path = f"temp/{output.stem}.{chunk_index}.tmp"

            start_chunk = chunk_size * chunk_index
            end_chunk = chunk_size * (chunk_index + 1)

            range_header = _HEADERS.copy()
            range_header['Range'] = f"bytes={start_chunk}-{end_chunk - 1}"
            try:
                async with session.get(link, headers=range_header, allow_redirects=True, chunked=True,
                                       timeout=None) as r:
                    async with aiofiles.open(chunk_path, 'wb') as f:
                        async for chunk, _ in r.content.iter_chunks():
                            await f.write(chunk)
                            progress.update(len(chunk))

                            if self.progress_callback and progress.should_update():
                                await self.progress_callback(progress.value, total_size)

            except requests.exceptions.RequestException as e:
                print(e)

        def add_to_event_loop(j):
            return asyncio.get_event_loop().create_task(download_chunk(j))

        tasks = map(add_to_event_loop, range(self.connections))
        await asyncio.gather(*tasks)

        with open(output, 'wb') as fm:
            for i in range(self.connections):
                temp_path = f"temp/{output.stem}.{i}.tmp"
                with open(temp_path, 'rb') as fi:
                    shutil.copyfileobj(fi, fm)
                os.remove(temp_path)

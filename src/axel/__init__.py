__author__ = """Aria Bagheri"""
__email__ = 'ariab9342@gmail.com'
__version__ = '1.0.1'

import math
import os
import pathlib
import shutil
from multiprocessing.pool import ThreadPool
from typing import Callable

import requests

_HEADERS = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/1.0.1.94 Safari/537.36'
}


class _Progress:
    value: int = 0

    def __init__(self):
        pass

    def update(self, v: int):
        self.value += v


class Axel:
    block_size = 5368709 * 2
    connections: int = 64
    progress_callback: Callable[[int, int], None] = None

    def __init__(self, block_size: int = 5368709 * 2, connections: 64 = 64, progress_callback: Callable[[int, int], None] = None):
        self.block_size = block_size
        self.connections = connections
        self.progress_callback = progress_callback

    def download_file(self, link: str, output: str):
        output_path = pathlib.Path(output)
        if output_path.is_dir():
            raise Exception("Output is not a file!")
        os.makedirs("temp/", exist_ok=True)

        download_head = requests.head(link)
        accept_ranges = 'accept-ranges' in download_head.headers and 'bytes' in download_head.headers['accept-ranges']

        total_size = int(requests.head(link).headers['content-length'])

        if not accept_ranges:
            self._download_file_slow(link, output, total_size)
        else:
            self._download_file_multithread(link, output_path, total_size)

    def _download_file_slow(self, link: str, output: str, total_size: int):
        progress = _Progress()
        with requests.get(link, allow_redirects=True, stream=True) as r:
            with open(output, 'wb') as f:
                for chunk in r.iter_content(chunk_size=self.block_size):
                    f.write(chunk)
                    progress.update(len(chunk))
                    self.progress_callback(progress.value, total_size)

    def _download_file_multithread(self, link: str, output: pathlib.Path, total_size: int):
        chunk_size = math.ceil(total_size / self.connections)
        progress = _Progress()

        def download_chunk(chunk_index):
            chunk_path = f"temp/{output.stem}.{chunk_index}.tmp"
            if os.path.exists(chunk_path):
                already_chunk = os.path.getsize(chunk_path)
            else:
                already_chunk = 0

            start_chunk = chunk_size * chunk_index + already_chunk
            end_chunk = chunk_size * (chunk_index + 1)

            range_header = _HEADERS.copy()
            range_header['Range'] = f"bytes={start_chunk}-{end_chunk - 1}"

            try:
                with requests.get(link, headers=range_header, timeout=30,
                                  allow_redirects=True, stream=True) as r:
                    with open(chunk_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=self.block_size):
                            f.write(chunk)
                            progress.update(len(chunk))
                            self.progress_callback(progress.value, total_size)

            except requests.exceptions.RequestException as e:
                print(e)

        with ThreadPool() as pool:
            pool.map(download_chunk, range(self.connections))

        with open(output, 'wb') as fm:
            for i in range(self.connections):
                temp_path = f"temp/{output.stem}.{i}.tmp"
                with open(temp_path, 'rb') as fi:
                    shutil.copyfileobj(fi, fm, self.block_size)
                os.remove(temp_path)

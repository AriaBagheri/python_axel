__author__ = """Aria Bagheri"""
__email__ = 'ariab9342@gmail.com'
__version__ = '1.0.0'

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
_BLOCK_SIZE = 1024


class _Progress:
    value: int = 0

    def __init__(self):
        pass

    def update(self, v: int):
        self.value += v


class Axel:
    def __init__(self):
        pass

    def download_file(self, download_link: str, output: str, connections: int = 64,
                      progress_callback: Callable[[int, int], None] = None):
        output_path = pathlib.Path(output)
        if output_path.is_dir():
            raise Exception("Output is not a file!")
        os.makedirs("temp/", exist_ok=True)

        download_head = requests.head(download_link)
        accept_ranges = 'accept-ranges' in download_head.headers and 'bytes' in download_head.headers['accept-ranges']

        total_size = int(requests.head(download_link).headers['content-length'])

        if not accept_ranges:
            self._download_file_slow(download_link, output, total_size, progress_callback)
        else:
            self._download_file_multithread(download_link, output_path, total_size, connections, progress_callback)

    @staticmethod
    def _download_file_slow(download_link: str, output: str, total_size: int,
                            progress_callback: Callable[[int, int], None] = None):
        progress = _Progress()
        with requests.get(download_link, allow_redirects=True, stream=True) as r:
            with open(output, 'wb') as f:
                for chunk in r.iter_content(chunk_size=_BLOCK_SIZE):
                    f.write(chunk)
                    progress.update(len(chunk))
                    progress_callback(progress.value, total_size)

    @staticmethod
    def _download_file_multithread(download_link: str, output: pathlib.Path, total_size: int, total_connections: int,
                                   progress_callback: Callable[[int, int], None] = None):
        chunk_size = math.ceil(total_size / total_connections)
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
                with requests.get(download_link, headers=range_header, timeout=30,
                                  allow_redirects=True, stream=True) as r:
                    with open(chunk_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=_BLOCK_SIZE):
                            f.write(chunk)
                            progress.update(len(chunk))
                            progress_callback(progress.value, total_size)

            except requests.exceptions.RequestException as e:
                print(e)

        with ThreadPool() as pool:
            pool.map(download_chunk, range(total_connections))

        with open(output, 'wb') as fm:
            for i in range(total_connections):
                temp_path = f"temp/{output.stem}.{i}.tmp"
                with open(temp_path, 'rb') as fi:
                    shutil.copyfileobj(fi, fm, _BLOCK_SIZE)
                os.remove(temp_path)

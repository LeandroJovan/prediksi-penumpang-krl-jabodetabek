import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

from backend.app.core.errors import AppError

_lock = threading.Lock()
_inflight = 0
_executor: ThreadPoolExecutor | None = None
_executor_size = 0


def _get_executor(size: int) -> ThreadPoolExecutor:
    global _executor, _executor_size
    with _lock:
        if _executor is None or _executor_size != size:
            _executor = ThreadPoolExecutor(max_workers=size, thread_name_prefix="inference")
            _executor_size = size
        return _executor


def _release(_future) -> None:
    global _inflight
    with _lock:
        _inflight -= 1


async def run_inference(fn, *args, timeout: float, max_concurrency: int):
    """Jalankan inferensi di pool terbatas.

    ``asyncio.wait_for`` pada thread tidak menghentikan thread-nya; tanpa batas, request yang timeout
    menumpuk thread yang masih berjalan. Slot dilepas saat thread BENAR-BENAR selesai, dan bila semua
    slot terpakai request baru ditolak cepat (503) sehingga pemanggil jatuh ke fallback.
    """
    global _inflight
    with _lock:
        if _inflight >= max_concurrency:
            raise AppError("INFERENCE_BUSY", 503, "Inference capacity is exhausted.")
        _inflight += 1
    try:
        future = _get_executor(max_concurrency).submit(fn, *args)
    except BaseException:
        with _lock:
            _inflight -= 1
        raise
    future.add_done_callback(_release)
    return await asyncio.wait_for(asyncio.wrap_future(future), timeout=timeout)

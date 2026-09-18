from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator


def _tqdm(total=None, desc: str = "", unit: str = "it", leave: bool = True, **kwargs):
    try:
        from tqdm import tqdm
    except Exception:
        return _NullBar(total=total, desc=desc)
    return tqdm(total=total, desc=desc, unit=unit, leave=leave, dynamic_ncols=True, **kwargs)


class _NullBar:
    def __init__(self, total=None, desc: str = ""):
        self.total = total
        self.n = 0
        self.desc = desc

    def update(self, n: int = 1) -> None:
        self.n += n

    def set_postfix(self, **kwargs) -> None:
        return None

    def set_description(self, desc: str, refresh: bool = True) -> None:
        self.desc = desc

    def close(self) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


@contextmanager
def progress(total=None, desc: str = "", unit: str = "it", disable: bool = False, leave: bool = True) -> Iterator:
    bar = _NullBar(total=total, desc=desc) if disable else _tqdm(total=total, desc=desc, unit=unit, leave=leave)
    try:
        yield bar
    finally:
        bar.close()

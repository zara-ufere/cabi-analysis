"""Download Capital Bikeshare monthly trip files.

Files are published as one zip per month, named YYYYMM-capitalbikeshare-tripdata.zip, in a public
S3 bucket. The raw files are covered by the Capital Bikeshare data license agreement, so this repo
downloads them on demand into data/ (which is git-ignored) and never stores them.
"""
from __future__ import annotations

import os
import re
import shutil
import urllib.error
import urllib.request
import zipfile
from typing import Callable, Iterator, List, Optional

BASE_URL = "https://s3.amazonaws.com/capitalbikeshare-data"
MONTH_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


class DownloadError(RuntimeError):
    pass


def parse_month(text: str) -> tuple:
    m = MONTH_RE.match(text)
    if not m:
        raise ValueError("month must look like 2025-03, got %r" % text)
    return int(m.group(1)), int(m.group(2))


def months_between(start: str, end: str) -> List[str]:
    """Inclusive list of 'YYYY-MM' strings from start to end."""
    (y, m), (ey, em) = parse_month(start), parse_month(end)
    if (y, m) > (ey, em):
        raise ValueError("start month %s is after end month %s" % (start, end))
    out = []
    while (y, m) <= (ey, em):
        out.append("%04d-%02d" % (y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def file_name(month: str) -> str:
    y, m = parse_month(month)
    return "%04d%02d-capitalbikeshare-tripdata.zip" % (y, m)


def month_url(month: str, base_url: str = BASE_URL) -> str:
    return "%s/%s" % (base_url.rstrip("/"), file_name(month))


def fetch_month(month: str, dest_dir: str, base_url: str = BASE_URL, force: bool = False,
                opener: Optional[Callable] = None, timeout: int = 120) -> str:
    """Download one month. Returns the local path. Raises DownloadError with a plain message."""
    os.makedirs(dest_dir, exist_ok=True)
    target = os.path.join(dest_dir, file_name(month))
    if not force and os.path.exists(target) and zipfile.is_zipfile(target):
        return target
    url = month_url(month, base_url)
    partial = target + ".part"
    open_url = opener or (lambda u: urllib.request.urlopen(u, timeout=timeout))
    try:
        with open_url(url) as response, open(partial, "wb") as out:
            shutil.copyfileobj(response, out)
    except urllib.error.HTTPError as exc:
        _discard(partial)
        if exc.code in (403, 404):
            raise DownloadError("%s is not published (HTTP %d). Newer months appear a few weeks after they end." % (
                file_name(month), exc.code))
        raise DownloadError("%s: server returned HTTP %d" % (url, exc.code))
    except (urllib.error.URLError, OSError) as exc:
        _discard(partial)
        raise DownloadError("could not reach %s (%s)" % (url, getattr(exc, "reason", exc)))
    if not zipfile.is_zipfile(partial):
        _discard(partial)
        raise DownloadError("%s did not download as a valid zip file" % file_name(month))
    os.replace(partial, target)
    return target


def _discard(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def fetch_range(start: str, end: str, dest_dir: str, **kwargs) -> Iterator[tuple]:
    """Yield (month, path_or_None, error_or_None) so one missing month does not stop the rest."""
    for month in months_between(start, end):
        try:
            yield month, fetch_month(month, dest_dir, **kwargs), None
        except DownloadError as exc:
            yield month, None, str(exc)

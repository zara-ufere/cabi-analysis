import http.server
import os
import threading
import zipfile

import pytest

from conftest import trip, write_zip
from cabi import download


def test_months_between_handles_year_wrap_and_single_month():
    assert download.months_between("2025-11", "2026-02") == ["2025-11", "2025-12", "2026-01", "2026-02"]
    assert download.months_between("2026-02", "2026-02") == ["2026-02"]
    assert len(download.months_between("2024-01", "2025-12")) == 24


@pytest.mark.parametrize("bad", ["2026-13", "2026-00", "202602", "2026-2", "feb 2026", ""])
def test_bad_month_strings_are_rejected(bad):
    with pytest.raises(ValueError):
        download.parse_month(bad)


def test_reversed_range_is_an_error():
    with pytest.raises(ValueError, match="after"):
        download.months_between("2026-03", "2026-02")


def test_file_name_and_url():
    assert download.file_name("2026-02") == "202602-capitalbikeshare-tripdata.zip"
    assert download.month_url("2026-02", "http://x/y/") == "http://x/y/202602-capitalbikeshare-tripdata.zip"


@pytest.fixture
def server(tmp_path):
    """A local web server that behaves like the bucket: good zip for 2026-02, junk for 2026-03, 404 otherwise."""
    root = tmp_path / "bucket"
    root.mkdir()
    write_zip(root / "202602-capitalbikeshare-tripdata.zip", [trip("R1")])
    (root / "202603-capitalbikeshare-tripdata.zip").write_bytes(b"<html>not a zip</html>")
    hits = []

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(root), **k)

        def log_message(self, *args):
            hits.append(self.path)

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield "http://127.0.0.1:%d" % httpd.server_address[1], hits
    httpd.shutdown()


def test_download_success_skip_and_force(server, tmp_path):
    base, hits = server
    dest = str(tmp_path / "raw")
    path = download.fetch_month("2026-02", dest, base_url=base)
    assert zipfile.is_zipfile(path) and os.path.basename(path) == "202602-capitalbikeshare-tripdata.zip"
    assert len(hits) == 1
    download.fetch_month("2026-02", dest, base_url=base)                 # already there: no second request
    assert len(hits) == 1
    download.fetch_month("2026-02", dest, base_url=base, force=True)
    assert len(hits) == 2
    assert not [f for f in os.listdir(dest) if f.endswith(".part")]


def test_missing_month_gives_plain_message(server, tmp_path):
    base, _ = server
    with pytest.raises(download.DownloadError, match="not published"):
        download.fetch_month("2031-01", str(tmp_path / "raw"), base_url=base)


def test_non_zip_response_is_rejected_and_cleaned_up(server, tmp_path):
    base, _ = server
    dest = str(tmp_path / "raw")
    with pytest.raises(download.DownloadError, match="valid zip"):
        download.fetch_month("2026-03", dest, base_url=base)
    assert os.listdir(dest) == []


def test_corrupt_existing_file_is_downloaded_again(server, tmp_path):
    base, hits = server
    dest = tmp_path / "raw"
    dest.mkdir()
    (dest / "202602-capitalbikeshare-tripdata.zip").write_bytes(b"truncated")
    path = download.fetch_month("2026-02", str(dest), base_url=base)
    assert zipfile.is_zipfile(path) and len(hits) == 1


def test_range_keeps_going_after_one_failure(server, tmp_path):
    base, _ = server
    results = list(download.fetch_range("2026-01", "2026-03", str(tmp_path / "raw"), base_url=base))
    assert [(m, p is not None) for m, p, e in results] == [("2026-01", False), ("2026-02", True), ("2026-03", False)]
    assert "not published" in results[0][2] and "valid zip" in results[2][2]


def test_unreachable_server_is_a_download_error(tmp_path):
    with pytest.raises(download.DownloadError, match="could not reach"):
        download.fetch_month("2026-02", str(tmp_path), base_url="http://127.0.0.1:1", timeout=2)

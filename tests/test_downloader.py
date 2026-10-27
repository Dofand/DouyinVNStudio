"""Unit tests for Douyin downloader adapter and URL parsing."""

from pathlib import Path
import pytest
from core.downloader import DownloaderAdapter


def test_extract_url_clean():
    adapter = DownloaderAdapter()
    url = "https://v.douyin.com/iABCxyz/"
    extracted = adapter.extract_url(url)
    assert extracted == "https://v.douyin.com/iABCxyz/"


def test_extract_url_from_share_text():
    adapter = DownloaderAdapter()
    raw_share = "7.12 复制打开抖音，看看【小明同学的作品】 https://v.douyin.com/iQWE123/ 04/23 l@s.pm"
    extracted = adapter.extract_url(raw_share)
    assert extracted == "https://v.douyin.com/iQWE123/"


def test_extract_url_none():
    adapter = DownloaderAdapter()
    assert adapter.extract_url("Không có link nào ở đây") is None
    assert adapter.extract_url("") is None


def test_download_invalid_url():
    adapter = DownloaderAdapter()
    with pytest.raises(ValueError, match="Không tìm thấy URL hợp lệ"):
        adapter.download("văn bản không hợp lệ", task_id="test1234")

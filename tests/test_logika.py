import pytest
import logika


def test_format_jadwal_kosong():
    teks = logika.format_jadwal("Yogyakarta", None)
    assert "Gagal mengambil jadwal" in teks


def test_format_jadwal_valid():
    sample_timings = {
        "Subuh": "04:15",
        "Dzuhur": "11:35",
        "Ashar": "14:55",
        "Maghrib": "17:40",
        "Isya": "18:50",
    }
    teks = logika.format_jadwal("Yogyakarta", sample_timings)
    assert "Yogyakarta" in teks
    assert "**Subuh**: 04:15" in teks
    assert "**Maghrib**: 17:40" in teks
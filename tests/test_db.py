import pytest
import db


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "uji_sholat.db"
    db.siapkan(p)
    return p


def test_default_city_if_not_set(path):
    # User 999 belum diset kotanya, harusnya default Yogyakarta
    kota = db.get_user_city(999, path=path)
    assert kota == "Yogyakarta"


def test_set_and_get_user_city(path):
    db.set_user_city(123, "Jakarta", path=path)
    kota = db.get_user_city(123, path=path)
    assert kota == "Jakarta"

def test_catat_selesai_hanya_jika_sesi_aktif_dan_belum_kedaluwarsa(path):
    from datetime import datetime, timedelta, timezone

    sekarang = datetime.now(timezone.utc)
    akhir = sekarang + timedelta(minutes=30)
    db.buat_sesi(
        321, "2026-11-09", "Subuh", 321, akhir.isoformat(), path=path
    )
    berhasil = db.catat_selesai(
        321, "2026-11-09", "Subuh", sekarang.isoformat(), path=path
    )
    assert berhasil is True
    assert db.get_sesi(321, "2026-11-09", "Subuh", path=path) is None
    rows = db.get_riwayat(
        321, "2026-11-09", "2026-11-09", path=path
    )
    assert len(rows) == 1
    assert rows[0]["prayer"] == "Subuh"


def test_sesi_kedaluwarsa_tidak_masuk_riwayat(path):
    from datetime import datetime, timedelta, timezone

    sekarang = datetime.now(timezone.utc)
    akhir = sekarang - timedelta(minutes=1)
    db.buat_sesi(
        654, "2026-11-09", "Dzuhur", 654, akhir.isoformat(), path=path
    )
    berhasil = db.catat_selesai(
        654, "2026-11-09", "Dzuhur", sekarang.isoformat(), path=path
    )
    assert berhasil is False
    assert db.get_riwayat(
        654, "2026-11-09", "2026-11-09", path=path
    ) == []

"""Pengambilan dan pengolahan jadwal sholat dari Aladhan API."""
from datetime import date, datetime
import requests

BASE_URL = "https://api.aladhan.com/v1"


def _ambil_timings(city, tanggal=None):
    try:
        if tanggal:
            tanggal_api = tanggal.strftime("%d-%m-%Y")
            url = f"{BASE_URL}/timingsByCity/{tanggal_api}"
        else:
            url = f"{BASE_URL}/timingsByCity"
        response = requests.get(
            url,
            params={"city": city, "country": "Indonesia", "method": 11},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 200:
            return None
        return payload["data"]["timings"]
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def _jam(value):
    """Ambil HH:MM dari nilai API, termasuk jika ada keterangan zona."""
    if not value:
        return None
    try:
        return datetime.strptime(str(value).strip()[:5], "%H:%M").strftime("%H:%M")
    except ValueError:
        return None


def get_jadwal_sholat(city="Yogyakarta", tanggal=None):
    """Mengambil lima waktu sholat dan Sunrise untuk tanggal tertentu."""
    raw = _ambil_timings(city, tanggal)
    if not raw:
        return None
    return {
        "Subuh": _jam(raw.get("Fajr")),
        "Dzuhur": _jam(raw.get("Dhuhr")),
        "Ashar": _jam(raw.get("Asr")),
        "Maghrib": _jam(raw.get("Maghrib")),
        "Isya": _jam(raw.get("Isha")),
        "Terbit": _jam(raw.get("Sunrise")),
    }


def get_batas_sholat(city, tanggal, timings=None):
    """Mengembalikan batas akhir tiap sholat sebagai HH:MM.

    Subuh berakhir saat matahari terbit; sholat lainnya berakhir saat
    waktu sholat berikutnya masuk. Isya berakhir saat Subuh hari berikutnya.
    """
    from datetime import timedelta

    timings = timings or get_jadwal_sholat(city, tanggal)
    if not timings:
        return None

    besok = get_jadwal_sholat(city, tanggal + timedelta(days=1))
    if not besok:
        return None

    return {
        "Subuh": timings.get("Terbit"),
        "Dzuhur": timings.get("Ashar"),
        "Ashar": timings.get("Maghrib"),
        "Maghrib": timings.get("Isya"),
        "Isya": besok.get("Subuh"),
    }


def format_jadwal(city, timings):
    if not timings:
        return f"Gagal mengambil jadwal sholat untuk kota {city}. Coba lagi nanti atau periksa nama kota."
    nama_sholat = ["Subuh", "Dzuhur", "Ashar", "Maghrib", "Isya"]
    teks = f"📅 Jadwal Sholat Kota {city}\n\n"
    for sholat in nama_sholat:
        waktu = timings.get(sholat)
        if waktu:
            teks += f"• **{sholat}**: {waktu}\n"
    return teks

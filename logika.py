"""Pengambilan jadwal sholat dan timezone lokal dari Aladhan API."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import requests

BASE_URL = "https://api.aladhan.com/v1"
DEFAULT_COUNTRY = "Indonesia"

def pecah_lokasi(lokasi):
    """Menerima 'Yogyakarta' atau 'Cairo, Egypt'."""
    bagian = [x.strip() for x in str(lokasi).split(",", 1)]
    if len(bagian) == 1:
        return bagian[0], DEFAULT_COUNTRY
    if not all(bagian):
        return None, None
    return bagian[0], bagian[1]

def _ambil_data(city, country, tanggal=None):
    try:
        endpoint = f"{BASE_URL}/timingsByCity"
        if tanggal:
            endpoint += f"/{tanggal.strftime('%d-%m-%Y')}"
        response = requests.get(
            endpoint,
            params={"city": city, "country": country, "method": 11},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 200:
            return None
        return payload["data"]
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None

def _jam(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value).strip()[:5], "%H:%M").strftime("%H:%M")
    except ValueError:
        return None

def get_timezone(lokasi="Yogyakarta"):
    city, country = pecah_lokasi(lokasi)
    if not city:
        return None
    data = _ambil_data(city, country)
    if not data:
        return None
    nama_tz = data.get("meta", {}).get("timezone")
    if not nama_tz:
        return None
    try:
        return ZoneInfo(nama_tz)
    except ZoneInfoNotFoundError:
        return None

def get_jadwal_sholat(lokasi="Yogyakarta", tanggal=None):
    city, country = pecah_lokasi(lokasi)
    if not city:
        return None
    data = _ambil_data(city, country, tanggal)
    if not data:
        return None
    raw = data.get("timings", {})
    return {
        "Subuh": _jam(raw.get("Fajr")),
        "Dzuhur": _jam(raw.get("Dhuhr")),
        "Ashar": _jam(raw.get("Asr")),
        "Maghrib": _jam(raw.get("Maghrib")),
        "Isya": _jam(raw.get("Isha")),
        "Terbit": _jam(raw.get("Sunrise")),
    }

def get_batas_sholat(lokasi, tanggal, timings=None):
    timings = timings or get_jadwal_sholat(lokasi, tanggal)
    if not timings:
        return None
    besok = get_jadwal_sholat(lokasi, tanggal + timedelta(days=1))
    if not besok:
        return None
    return {
        "Subuh": timings.get("Terbit"),
        "Dzuhur": timings.get("Ashar"),
        "Ashar": timings.get("Maghrib"),
        "Maghrib": timings.get("Isya"),
        "Isya": besok.get("Subuh"),
    }

def format_jadwal(lokasi, timings):
    if not timings:
        return f"Gagal mengambil jadwal sholat untuk {lokasi}. Periksa penulisan kota dan negara."
    teks = f"📅 Jadwal Sholat {lokasi}\\n\\n"
    for nama in ("Subuh", "Dzuhur", "Ashar", "Maghrib", "Isya"):
        if timings.get(nama):
            teks += f"• **{nama}**: {timings[nama]}\\n"
    return teks

"""Penyimpanan pengguna, sesi pengingat aktif, dan riwayat sholat."""
import sqlite3
from contextlib import contextmanager

DB_PATH = "sholat.db"


@contextmanager
def koneksi(path=DB_PATH):
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    try:
        with con:
            yield con
    finally:
        con.close()


def siapkan(path=DB_PATH):
    with koneksi(path) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                city TEXT NOT NULL DEFAULT 'Yogyakarta',
                chat_id INTEGER
            )
        """)
        # Migrasi database lama yang belum memiliki kolom chat_id.
        kolom = {row["name"] for row in con.execute("PRAGMA table_info(users)")}
        if "chat_id" not in kolom:
            con.execute("ALTER TABLE users ADD COLUMN chat_id INTEGER")

        con.execute("""
            CREATE TABLE IF NOT EXISTS prayer_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                prayer_date TEXT NOT NULL,
                prayer TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                UNIQUE(user_id, prayer_date, prayer)
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS active_sessions (
                user_id INTEGER NOT NULL,
                prayer_date TEXT NOT NULL,
                prayer TEXT NOT NULL,
                chat_id INTEGER NOT NULL,
                end_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                PRIMARY KEY(user_id, prayer_date, prayer)
            )
        """)


def ensure_user(user_id, chat_id, path=DB_PATH):
    with koneksi(path) as con:
        con.execute("""
            INSERT INTO users (user_id, city, chat_id)
            VALUES (?, 'Yogyakarta', ?)
            ON CONFLICT(user_id) DO UPDATE SET chat_id=excluded.chat_id
        """, (user_id, chat_id))


def set_user_city(user_id, city, path=DB_PATH):
    with koneksi(path) as con:
        con.execute("""
            INSERT INTO users (user_id, city) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET city=excluded.city
        """, (user_id, city))


def get_user_city(user_id, path=DB_PATH):
    with koneksi(path) as con:
        row = con.execute(
            "SELECT city FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["city"] if row else "Yogyakarta"


def get_all_users(path=DB_PATH):
    with koneksi(path) as con:
        return [dict(row) for row in con.execute(
            "SELECT user_id, city, chat_id FROM users WHERE chat_id IS NOT NULL"
        ).fetchall()]


def buat_sesi(user_id, prayer_date, prayer, chat_id, end_at, path=DB_PATH):
    with koneksi(path) as con:
        con.execute("""
            INSERT INTO active_sessions
                (user_id, prayer_date, prayer, chat_id, end_at, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
            ON CONFLICT(user_id, prayer_date, prayer) DO UPDATE SET
                chat_id=excluded.chat_id, end_at=excluded.end_at, status='pending'
        """, (user_id, prayer_date, prayer, chat_id, end_at))


def get_sesi(user_id, prayer_date, prayer, path=DB_PATH):
    with koneksi(path) as con:
        row = con.execute("""
            SELECT * FROM active_sessions
            WHERE user_id=? AND prayer_date=? AND prayer=? AND status='pending'
        """, (user_id, prayer_date, prayer)).fetchone()
        return dict(row) if row else None


def hapus_sesi(user_id, prayer_date, prayer, path=DB_PATH):
    with koneksi(path) as con:
        con.execute("""
            DELETE FROM active_sessions
            WHERE user_id=? AND prayer_date=? AND prayer=?
        """, (user_id, prayer_date, prayer))


def catat_selesai(user_id, prayer_date, prayer, completed_at, path=DB_PATH):
    """Simpan hanya konfirmasi selesai yang dilakukan sebelum batas waktu."""
    with koneksi(path) as con:
        row = con.execute("""
            SELECT end_at FROM active_sessions
            WHERE user_id=? AND prayer_date=? AND prayer=? AND status='pending'
        """, (user_id, prayer_date, prayer)).fetchone()
        if not row or completed_at > row["end_at"]:
            return False
        con.execute("""
            INSERT OR IGNORE INTO prayer_logs
                (user_id, prayer_date, prayer, completed_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, prayer_date, prayer, completed_at))
        con.execute("""
            DELETE FROM active_sessions
            WHERE user_id=? AND prayer_date=? AND prayer=?
        """, (user_id, prayer_date, prayer))
        return True


def get_riwayat(user_id, tanggal_awal, tanggal_akhir, path=DB_PATH):
    with koneksi(path) as con:
        rows = con.execute("""
            SELECT prayer_date, prayer, completed_at
            FROM prayer_logs
            WHERE user_id=? AND prayer_date>=? AND prayer_date<=?
            ORDER BY prayer_date, completed_at
        """, (user_id, tanggal_awal, tanggal_akhir)).fetchall()
        return [dict(row) for row in rows]

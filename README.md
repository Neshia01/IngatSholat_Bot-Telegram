# SholatBot

Bot Telegram pengingat waktu sholat dengan jadwal otomatis, tombol konfirmasi, snooze, dan riwayat.

## Fitur

- `/start`: sapaan dan aktivasi pengingat otomatis.
- `/help`: panduan penggunaan.
- `/jadwal`: jadwal sholat hari ini.
- `/setkota Yogyakarta`: mengganti kota dan memasang ulang jadwal.
- `/riwayat`: rekap hari ini.
- `/riwayat minggu` dan `/riwayat bulan`: rekap mingguan dan bulanan.
- Tombol **Sudah Sholat** menyimpan konfirmasi ke database.
- Tombol **Tunda 15 Menit** mengirim pengingat susulan, maksimal sampai batas waktu sholat.
- Peringatan 30 menit sebelum waktu sholat berakhir.
- Jadwal diperbarui otomatis setiap hari dan dipulihkan ketika bot dijalankan ulang.

## Instalasi (Windows / PowerShell)

1. Buat virtual environment:

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

2. Install dependency:

   ```powershell
   pip install -r requirements.txt
   ```

3. Salin `.env.example` menjadi `.env`, lalu isi token bot:

   ```env
   BOT_TOKEN=TOKEN_DARI_BOTFATHER
   ```

4. Jalankan:

   ```powershell
   python bot.py
   ```

5. Buka bot Telegram, lalu kirim `/start`.

## Batas waktu sholat yang digunakan

- Subuh berakhir saat matahari terbit.
- Dzuhur berakhir saat Ashar masuk.
- Ashar berakhir saat Maghrib masuk.
- Maghrib berakhir saat Isya masuk.
- Isya berakhir saat Subuh hari berikutnya.

Batas Isya dapat mengikuti ketentuan fikih/otoritas yang ingin dipakai; saat ini implementasi menggunakan Subuh berikutnya sebagai batas.

## Database

SQLite menggunakan file `sholat.db`. Tabel `prayer_logs` hanya menyimpan sholat yang dikonfirmasi selesai. Sesi yang tidak dikonfirmasi sampai batas waktu dihapus dari `active_sessions` dan tidak dihitung sebagai sholat selesai.

Jangan membagikan file `.env` karena berisi token bot.

## Pengujian

Jalankan:

```powershell
pytest -q
```

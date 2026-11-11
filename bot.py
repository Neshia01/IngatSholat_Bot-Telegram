"""SholatBot: pengingat waktu sholat dan pencatat konfirmasi sholat."""
import logging
import os
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import (
    BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
)
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, ContextTypes
)

import db
import logika

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("sholatbot")

DEFAULT_TIMEZONE = ZoneInfo('Asia/Jakarta')
NAMA_SHOLAT = ["Subuh", "Dzuhur", "Ashar", "Maghrib", "Isya"]
SLUG = {
    "Subuh": "subuh", "Dzuhur": "dzuhur", "Ashar": "ashar",
    "Maghrib": "maghrib", "Isya": "isya",
}
DARI_SLUG = {v: k for k, v in SLUG.items()}

BANTUAN = (
    "🤖 PANDUAN SHOLATBOT\n\n"
    "/start - Memulai atau mengaktifkan pengingat\n"
    "/jadwal - Melihat jadwal sholat hari ini\n"
    "/setkota kota, negara - Mengubah lokasi (contoh: Cairo, Egypt)\n"
    "/riwayat - Melihat riwayat sholat harian, mingguan, dan bulanan\n"
    "/help - Menampilkan panduan ini\n\n"
    "Saat notifikasi muncul, tekan Sudah Sholat setelah selesai, "
    "atau Tunda 15 Menit untuk menerima pengingat susulan."
)


def _db_path(context):
    return context.bot_data["db"]


def _timezone_user(context, user_id):
    kota = db.get_user_city(user_id, path=_db_path(context))
    return logika.get_timezone(kota) or DEFAULT_TIMEZONE


def _datetime_sholat(tanggal, jam, tz):
    jam_obj = datetime.strptime(jam, "%H:%M").time()
    return datetime.combine(tanggal, jam_obj, tzinfo=tz)


def _hapus_job_user(context, user_id):
    prefix = f"user:{user_id}:"
    for job in context.job_queue.jobs():
        if job.name and job.name.startswith(prefix):
            job.schedule_removal()


def _jadwalkan(context, callback, when, data, name):
    user_id = data.get("user_id") if isinstance(data, dict) else None
    tz = _timezone_user(context, user_id) if user_id else DEFAULT_TIMEZONE
    sekarang = datetime.now(tz)
    if when <= sekarang:
        return
    context.job_queue.run_once(
        callback, when=when, data=data, name=name
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    db.ensure_user(user.id, chat_id, path=_db_path(context))
    await atur_penjadwalan_user(context, user.id, chat_id)

    kota = db.get_user_city(user.id, path=_db_path(context))
    nama = user.first_name or "Teman"
    pesan = (
        f"Hai, {nama}! 👋\n\n"
        "Selamat datang di SholatBot. Aku akan membantumu mengingat "
        "waktu sholat dan mencatat sholat yang kamu konfirmasi selesai.\n\n"
        f"📍 Kota saat ini: {kota}\n\n"
        "Gunakan /jadwal untuk melihat jadwal hari ini, /riwayat untuk "
        "melihat catatan sholat, atau /help untuk melihat semua perintah.\n\n"
        "Semoga dimudahkan untuk menjaga sholat tepat waktu. 🤍"
    )
    await update.message.reply_text(pesan)


async def bantuan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(BANTUAN)


async def set_kota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Cara penggunaan: /setkota Yogyakarta\n"
            "Untuk luar negeri: /setkota Cairo, Egypt"
        )
        return

    kota_baru = " ".join(context.args).strip()
    timings = logika.get_jadwal_sholat(kota_baru)
    zona = logika.get_timezone(kota_baru)
    if not timings or not zona:
        await update.message.reply_text(
            f"Maaf, jadwal untuk kota '{kota_baru}' tidak ditemukan. "
            "Periksa ejaan nama kota, lalu coba lagi."
        )
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    db.ensure_user(user_id, chat_id, path=_db_path(context))
    db.set_user_city(user_id, kota_baru, path=_db_path(context))
    await atur_penjadwalan_user(context, user_id, chat_id)
    await update.message.reply_text(
        f"✅ Lokasi berhasil diubah menjadi {kota_baru}.\n"
        f"Zona waktu: {zona.key}\n"
        "Jadwal pengingat sudah diperbarui."
    )


async def cek_jadwal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    kota = db.get_user_city(user_id, path=_db_path(context))
    timings = logika.get_jadwal_sholat(kota)
    zona = logika.get_timezone(kota)
    teks = logika.format_jadwal(kota, timings)
    if zona:
        teks += f"\\nZona waktu: {zona.key}"
    await update.message.reply_text(teks, parse_mode="Markdown")


async def atur_penjadwalan_user(
    context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int
):
    """Pasang jadwal hari ini dan jadwalkan pembaruan untuk tengah malam."""
    db_path = _db_path(context)
    kota = db.get_user_city(user_id, path=db_path)
    _hapus_job_user(context, user_id)

    tz = _timezone_user(context, user_id)
    tanggal = datetime.now(tz).date()
    timings = logika.get_jadwal_sholat(kota, tanggal)
    if not timings:
        log.error("Gagal mengambil jadwal untuk user %s (%s)", user_id, kota)
        return

    batas = logika.get_batas_sholat(kota, tanggal, timings)
    if not batas:
        log.error("Gagal mengambil batas waktu sholat untuk %s", kota)
        return

    sekarang = datetime.now(tz)
    for nama in NAMA_SHOLAT:
        jam_mulai = timings.get(nama)
        jam_akhir = batas.get(nama)
        if not jam_mulai or not jam_akhir:
            continue

        mulai_dt = _datetime_sholat(tanggal, jam_mulai, tz)
        akhir_dt = _datetime_sholat(tanggal, jam_akhir, tz)
        if nama == "Isya" and akhir_dt <= mulai_dt:
            akhir_dt += timedelta(days=1)

        if akhir_dt <= sekarang:
            continue

        payload = {
            "user_id": user_id,
            "chat_id": chat_id,
            "prayer": nama,
            "prayer_date": tanggal.isoformat(),
            "end_at": akhir_dt.isoformat(),
        }
        prefix = f"user:{user_id}:{tanggal.isoformat()}:{SLUG[nama]}"

        _jadwalkan(
            context, kirim_notifikasi_sholat, mulai_dt, payload,
            f"{prefix}:start"
        )
        _jadwalkan(
            context, kirim_peringatan_30_menit,
            akhir_dt - timedelta(minutes=30), payload,
            f"{prefix}:warning"
        )
        _jadwalkan(
            context, akhiri_sesi, akhir_dt, payload,
            f"{prefix}:expiry"
        )

    besok_pukul = datetime.combine(
        tanggal + timedelta(days=1), time(0, 5), tzinfo=tz
    )
    _jadwalkan(
        context, perbarui_semua_jadwal_user, besok_pukul,
        {"user_id": user_id, "chat_id": chat_id},
        f"user:{user_id}:refresh"
    )
    log.info("Jadwal user %s (%s) berhasil dipasang.", user_id, kota)


async def perbarui_semua_jadwal_user(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    await atur_penjadwalan_user(context, data["user_id"], data["chat_id"])


def _keyboard(prayer, prayer_date):
    slug = SLUG[prayer]
    tanggal_singkat = prayer_date.replace("-", "")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "✅ Sudah Sholat",
            callback_data=f"done|{slug}|{tanggal_singkat}"
        )],
        [InlineKeyboardButton(
            "⏳ Tunda 15 Menit",
            callback_data=f"snooze|{slug}|{tanggal_singkat}"
        )],
    ])


async def kirim_notifikasi_sholat(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    now = datetime.now(_timezone_user(context, data['user_id']))
    end_at = datetime.fromisoformat(data["end_at"])
    if now >= end_at:
        return

    db.buat_sesi(
        data["user_id"], data["prayer_date"], data["prayer"],
        data["chat_id"], data["end_at"], path=_db_path(context)
    )
    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=(
            f"⏰ Waktu sholat {data['prayer']} telah tiba!\n\n"
            "Yuk, luangkan waktu untuk menunaikan sholat. 🤍"
        ),
        reply_markup=_keyboard(data["prayer"], data["prayer_date"]),
    )


async def kirim_pengingat_susulan(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    sesi = db.get_sesi(
        data["user_id"], data["prayer_date"], data["prayer"],
        path=_db_path(context)
    )
    if not sesi:
        return
    if datetime.now(_timezone_user(context, data["user_id"])) >= datetime.fromisoformat(sesi["end_at"]):
        db.hapus_sesi(
            data["user_id"], data["prayer_date"], data["prayer"],
            path=_db_path(context)
        )
        return

    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=(
            f"🔔 Pengingat sholat {data['prayer']}\n\n"
            "Kamu meminta untuk diingatkan kembali. Sudah siap menunaikan sholat?"
        ),
        reply_markup=_keyboard(data["prayer"], data["prayer_date"]),
    )


async def kirim_peringatan_30_menit(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    sesi = db.get_sesi(
        data["user_id"], data["prayer_date"], data["prayer"],
        path=_db_path(context)
    )
    if not sesi:
        return
    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=(
            f"⚠️ Waktu sholat {data['prayer']} akan berakhir dalam 30 menit.\n\n"
            "Jika belum, yuk segera tunaikan sholat."
        ),
        reply_markup=_keyboard(data["prayer"], data["prayer_date"]),
    )


async def akhiri_sesi(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    db.hapus_sesi(
        data["user_id"], data["prayer_date"], data["prayer"],
        path=_db_path(context)
    )


async def tombol_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        aksi, slug, tanggal_singkat = query.data.split("|")
        prayer = DARI_SLUG[slug]
        prayer_date = datetime.strptime(tanggal_singkat, "%Y%m%d").date().isoformat()
    except (ValueError, KeyError, AttributeError):
        await query.answer("Tombol tidak valid.", show_alert=True)
        return

    user_id = query.from_user.id
    chat_id = query.message.chat_id
    db_path = _db_path(context)
    sesi = db.get_sesi(user_id, prayer_date, prayer, path=db_path)

    if not sesi:
        await query.edit_message_text(
            f"ℹ️ Sesi pengingat {prayer} sudah berakhir atau tidak ditemukan."
        )
        return

    now = datetime.now(_timezone_user(context, user_id))
    batas = datetime.fromisoformat(sesi["end_at"])
    if now >= batas:
        db.hapus_sesi(user_id, prayer_date, prayer, path=db_path)
        await query.edit_message_text(
            f"⌛ Waktu sholat {prayer} sudah berakhir. Sesi ini tidak dicatat sebagai selesai."
        )
        return

    if aksi == "done":
        berhasil = db.catat_selesai(
            user_id, prayer_date, prayer, now.isoformat(), path=db_path
        )
        if berhasil:
            await query.edit_message_text(
                f"✅ Alhamdulillah, sholat {prayer} berhasil dicatat. "
                "Semoga istiqamah! 🤍"
            )
        else:
            await query.edit_message_text(
                "Sesi sudah tidak aktif sehingga tidak dapat dicatat."
            )

    elif aksi == "snooze":
        sisa = batas - now
        jeda = min(timedelta(minutes=15), sisa)
        if jeda.total_seconds() <= 0:
            await query.edit_message_text("Waktu sholat sudah berakhir.")
            return

        nama_job_snooze = f"snooze:{user_id}:{prayer_date}:{slug}"
        for job_lama in context.job_queue.get_jobs_by_name(nama_job_snooze):
            job_lama.schedule_removal()
        context.job_queue.run_once(
            kirim_pengingat_susulan,
            when=jeda,
            data={
                "user_id": user_id,
                "chat_id": chat_id,
                "prayer": prayer,
                "prayer_date": prayer_date,
            },
            name=nama_job_snooze,
        )
        await query.edit_message_text(
            f"⏳ Baik, aku akan mengingatkanmu kembali dalam "
            f"{max(1, int(jeda.total_seconds() // 60))} menit."
        )
    else:
        await query.edit_message_text("Aksi tidak dikenali.")


def _rentang_riwayat(periode, context, user_id):
    hari_ini = datetime.now(_timezone_user(context, user_id)).date()
    if periode == "hari":
        awal = akhir = hari_ini
        judul = "Hari Ini"
    elif periode == "minggu":
        awal = hari_ini - timedelta(days=hari_ini.weekday())
        akhir = hari_ini
        judul = "Minggu Ini"
    else:
        awal = hari_ini.replace(day=1)
        akhir = hari_ini
        judul = "Bulan Ini"
    return awal, akhir, judul


async def kirim_riwayat(update, context, periode):
    user_id = update.effective_user.id
    awal, akhir, judul = _rentang_riwayat(periode, context, user_id)
    rows = db.get_riwayat(
        user_id, awal.isoformat(), akhir.isoformat(), path=_db_path(context)
    )
    selesai = {}
    for row in rows:
        selesai.setdefault(row["prayer_date"], set()).add(row["prayer"])

    jumlah_selesai = sum(len(v) for v in selesai.values())
    jumlah_hari = (akhir - awal).days + 1
    jumlah_target = jumlah_hari * len(NAMA_SHOLAT)
    persentase = (jumlah_selesai / jumlah_target * 100) if jumlah_target else 0

    teks = (
        f"📊 RIWAYAT SHOLAT — {judul}\n"
        f"Periode: {awal.strftime('%d/%m/%Y')} - {akhir.strftime('%d/%m/%Y')}\n\n"
    )
    if periode == "hari":
        tanggal = awal.isoformat()
        tercatat = selesai.get(tanggal, set())
        for nama in NAMA_SHOLAT:
            teks += f"{'✅' if nama in tercatat else '—'} {nama}\n"
        teks += f"\nTercatat selesai: {len(tercatat)}/5 sholat."
    else:
        teks += f"Hari dalam periode: {jumlah_hari}\n"
        teks += f"Total sholat tercatat: {jumlah_selesai}/{jumlah_target}\n"
        teks += f"Rasio konfirmasi: {persentase:.1f}%\n\n"
        teks += "Rekap per hari:\n"
        for offset in range(jumlah_hari):
            tanggal = awal + timedelta(days=offset)
            tercatat = selesai.get(tanggal.isoformat(), set())
            teks += (
                f"• {tanggal.strftime('%d/%m')}: "
                f"{len(tercatat)}/5 sholat tercatat\n"
            )

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Harian", callback_data="history|hari"),
        InlineKeyboardButton("Mingguan", callback_data="history|minggu"),
        InlineKeyboardButton("Bulanan", callback_data="history|bulan"),
    ]])
    if update.callback_query:
        await update.callback_query.edit_message_text(
            teks, reply_markup=keyboard
        )
    else:
        await update.message.reply_text(teks, reply_markup=keyboard)


async def riwayat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    periode = context.args[0].lower() if context.args else "hari"
    if periode not in ("hari", "minggu", "bulan"):
        await update.message.reply_text(
            "Gunakan /riwayat, /riwayat minggu, atau /riwayat bulan."
        )
        return
    await kirim_riwayat(update, context, periode)


async def riwayat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    periode = query.data.split("|", 1)[1]
    await kirim_riwayat(update, context, periode)


async def setelah_mulai(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start", "Mulai atau aktifkan SholatBot"),
        BotCommand("jadwal", "Cek jadwal sholat hari ini"),
        BotCommand("riwayat", "Lihat riwayat sholat"),
        BotCommand("setkota", "Ubah kota lokasi"),
        BotCommand("help", "Panduan penggunaan bot"),
    ])

    # Pulihkan jadwal user setelah bot restart.
    for user in db.get_all_users(path=app.bot_data["db"]):
        await atur_penjadwalan_user(
            app, user["user_id"], user["chat_id"]
        )


def buat_aplikasi(token, db_path=db.DB_PATH):
    app = (
        Application.builder()
        .token(token)
        .post_init(setelah_mulai)
        .build()
    )
    app.bot_data["db"] = db_path
    db.siapkan(db_path)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", bantuan))
    app.add_handler(CommandHandler("setkota", set_kota))
    app.add_handler(CommandHandler("jadwal", cek_jadwal))
    app.add_handler(CommandHandler("riwayat", riwayat))
    app.add_handler(CallbackQueryHandler(riwayat_callback, pattern=r"^history\|"))
    app.add_handler(CallbackQueryHandler(tombol_callback, pattern=r"^(done|snooze)\|"))
    return app


def main():
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("BOT_TOKEN belum diisi di file .env!")
    app = buat_aplikasi(token)
    log.info("SholatBot berjalan...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()

import pytest
from telegram.ext import Application
import bot

def test_buat_aplikasi():
    """Memastikan fungsi buat_aplikasi berhasil merakit bot tanpa error."""
    token_dummy = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123eq"
    app = bot.buat_aplikasi(token_dummy)
    
    assert isinstance(app, Application)
    assert "db" in app.bot_data
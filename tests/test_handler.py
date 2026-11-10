import pytest
from telegram import Update
from telegram.ext import ContextTypes
import bot

@pytest.mark.asyncio
async def test_bantuan_text_format():
    """Memastikan string bantuan berisi perintah panduan yang benar."""
    assert "/jadwal" in bot.BANTUAN
    assert "/setkota" in bot.BANTUAN
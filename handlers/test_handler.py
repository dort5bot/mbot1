# handlers/test_handler.py
from aiogram import Router, types
from aiogram.filters import Command

router = Router()

@router.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("🤖 Bot çalışıyor! /start komudu alındı.")

@router.message(Command("ping"))
async def ping_handler(message: types.Message):
    await message.answer("🏓 Pong! Bot aktif.")

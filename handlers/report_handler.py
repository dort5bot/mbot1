from aiogram import Router, types
from aiogram.filters import Command

router = Router()

@router.message(Command("j"))
@router.message(Command("rapor"))
async def cmd_report(message: types.Message):
    await message.answer("📊 Rapor hazır!\n(Burada rapor içeriği olacak)")

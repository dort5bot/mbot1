# handlers/analysis_handler.py
"""
analysis/analysis_a.py
/t komutu ile tek coin analizi yapar.
"""

import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from analysis.analysis_a import get_analysis_aggregator
from utils.binance.binance_a import BinanceAPI

router = Router()
logger = logging.getLogger(__name__)

# Binance API örneği oluştur (production'da Singleton olabilir)
binance_api = BinanceAPI()
analyzer = get_analysis_aggregator(binance_api)


@router.message(Command("t"))
async def handle_single_coin_analysis(message: Message):
    """
    /t BTCUSDT gibi komutlara yanıt verir.
    Belirtilen sembol için analiz yapar ve sonuçları kullanıcıya gönderir.
    """
    try:
        args = message.text.strip().split()
        if len(args) < 2:
            await message.answer("❌ Lütfen sembol belirtin. Örnek: `/t BTCUSDT`", parse_mode="Markdown")
            return

        symbol = args[1].upper()

        await message.answer(f"📊 `{symbol}` için analiz başlatılıyor...", parse_mode="Markdown")

        result = await analyzer.run_analysis(symbol)

        module_scores = "\n".join(
            [f"• `{k}`: `{v:.2f}`" for k, v in result.module_scores.items()]
        )

        response = (
            f"✅ *{symbol}* için analiz tamamlandı\n"
            f"-----------------------------\n"
            f"{module_scores}\n"
            f"-----------------------------\n"
            f"*Alpha Signal:* `{result.alpha_signal_score:.2f}`\n"
            f"*Risk Score:* `{result.position_risk_score:.2f}`\n"
            f"*Gnosis Signal:* `{result.gnosis_signal:.2f}`\n\n"
            f"*Öneri:* `{result.recommendation}`\n"
            f"*Pozisyon Büyüklüğü:* `{result.position_size * 100:.0f}%`\n"
        )

        await message.answer(response, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"🛑 Analiz hatası: {e}")
        await message.answer("⚠️ Analiz sırasında bir hata oluştu.")

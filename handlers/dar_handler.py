# handlers/dar_handler.py
"""
# --------------------------------
# /dar      → Dosya ağacı (mesaj, uzun olursa TXT)
# /dar Z    → ZIP (tree.txt + içerikler, sadece listelenen dosyalar + .env + .gitignore)
# /dar k    → Alfabetik komut listesi (+ açıklamalar)
# /dar t    → Projedeki tüm geçerli dosyaların içeriği tek bir .txt dosyada
# dosya adi .env den alir TELEGRAM_NAME
"""

import asyncio
import logging
import os
import re
import zipfile
from datetime import datetime
from typing import List, Tuple, Dict

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from dotenv import load_dotenv

from handlers.DAR_INFO import DAR_INFO  # ✅ Komut açıklamaları

# Rate limiting - HTTP
load_dotenv()
TELEGRAM_NAME = os.getenv("TELEGRAM_NAME", "xbot")
ROOT_DIR = "."
TELEGRAM_MSG_LIMIT = 4000

logger = logging.getLogger(__name__)

EXT_LANG_MAP = {
    '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript', '.java': 'Java',
    '.cpp': 'C++', '.c': 'C', '.html': 'HTML', '.css': 'CSS', '.json': 'JSON',
    '.csv': 'CSV', '.sh': 'Shell', '.md': 'Markdown', '.txt': 'Text',
}

FILE_INFO = {
    'main.py': ("Ana bot başlatma, handler kayıtları, JobQueue görevleri", None),
    'keep_alive.py': ("Render Free ping sistemi (bot uyumasını önler)", None),
    'io_handler.py': ("/io → In-Out Alış Satış Baskısı raporu", "utils.io_utils"),
    'nls_handler.py': ("/nls → Balina hareketleri ve yoğunluk (NLS analizi)", None),
    'npr_handler.py': ("/npr → Nakit Piyasa Raporu", None),
    'eft_handler.py': ("/eft → ETF & ABD piyasaları", None),
    'ap_handler.py': ("/ap → Altların Güç Endeksi (AP)", "utils.ap_utils"),
    'price_handler.py': ("/p → Anlık fiyat, 24h değişim, hacim bilgisi", None),
    'p_handler.py': ("/p_ekle, /p_fav, /p_sil → Favori coin listesi yönetimi", None),
    'fr_handler.py': ("/fr → Funding Rate komutu ve günlük CSV kaydı", None),
    'whale_handler.py': ("/whale → Whale Alerts komutu ve günlük CSV kaydı", None),
    'binance_utils.py': ("Binance API'den veri çekme ve metrik fonksiyonlar", None),
    'csv_utils.py': ("CSV okuma/yazma ve Funding Rate, Whale CSV kayıt fonksiyonları", None),
    'trend_utils.py': ("Trend okları, yüzde değişim hesaplama ve formatlama", None),
    'fav_list.json': (None, None), '.env': (None, None), '.gitignore': (None, None),
    'runtime.txt': (None, None),
}


async def format_tree(root_dir: str) -> Tuple[str, List[str]]:
    """Proje dizin yapısını string olarak üretir ve geçerli dosyaları listeler."""
    tree_lines: List[str] = []
    valid_files: List[str] = []

    def walk(dir_path: str, prefix: str = "") -> None:
        items = sorted(os.listdir(dir_path))
        for i, item in enumerate(items):
            path = os.path.join(dir_path, item)
            connector = "└── " if i == len(items) - 1 else "├── "

            if os.path.isdir(path):
                if item.startswith("__") or (item.startswith(".") and item not in [".gitignore", ".env"]):
                    continue
                tree_lines.append(f"{prefix}{connector}{item}/")
                walk(path, prefix + ("    " if i == len(items) - 1 else "│   "))
            else:
                if item.startswith(".") and item not in [".env", ".gitignore"]:
                    continue
                ext = os.path.splitext(item)[1]
                if (ext not in EXT_LANG_MAP
                        and not item.endswith(('.txt', '.csv', '.json', '.md'))
                        and item not in [".env", ".gitignore"]):
                    continue
                desc, dep = FILE_INFO.get(item, (None, None))
                extra = f" # {desc}" if desc else ""
                extra += f" ♻️{dep}" if dep else ""
                tree_lines.append(f"{prefix}{connector}{item}{extra}")
                valid_files.append(path)

    await asyncio.to_thread(walk, root_dir)
    return "\n".join(tree_lines), valid_files


async def create_zip_with_tree_and_files(root_dir: str, zip_filename: str) -> str:
    """Proje dosyalarını ve tree.txt içeren bir zip dosyası oluşturur."""
    tree_text, valid_files = await format_tree(root_dir)
    try:
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr("tree.txt", tree_text)
            for filepath in valid_files:
                arcname = os.path.relpath(filepath, root_dir)
                try:
                    zipf.write(filepath, arcname)
                except Exception as e:
                    logger.warning(f"ZIP'e eklenemedi: {filepath} - {e}")
    except Exception as e:
        logger.exception("ZIP oluşturulurken hata")
        raise
    return zip_filename


async def scan_handlers_for_commands() -> Dict[str, str]:
    """handlers/ içindeki komutları ve açıklamaları döner."""
    commands: Dict[str, str] = {}
    handler_dir = os.path.join(ROOT_DIR, "handlers")

    handler_pattern = re.compile(r'CommandHandler\(\s*["\'](\w+)["\']')
    var_handler_pattern = re.compile(r'CommandHandler\(\s*(\w+)')
    command_pattern = re.compile(r'COMMAND\s*=\s*["\'](\w+)["\']')

    try:
        for fname in os.listdir(handler_dir):
            if not fname.endswith("_handler.py"):
                continue
            fpath = os.path.join(handler_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            matches = handler_pattern.findall(content)
            for cmd in matches:
                desc = DAR_INFO.get(cmd.lower(), "(?)")
                commands[f"/{cmd}"] = f"{desc} ({fname})"
            matches_var = var_handler_pattern.findall(content)
            if "COMMAND" in matches_var:
                cmd_match = command_pattern.search(content)
                if cmd_match:
                    cmd = cmd_match.group(1)
                    desc = DAR_INFO.get(cmd.lower(), "(?)")
                    commands[f"/{cmd}"] = f"{desc} ({fname})"
    except Exception as e:
        logger.exception("Komutlar taranamadı")
    return commands


async def dar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/dar komutu: Dosya ağacı, ZIP, komut listesi, içeriği metin olarak gönderme."""
    args = context.args
    mode = args[0].lower() if args else ""
    timestamp = datetime.now().strftime("%m%d_%H%M")

    if mode == "k":
        commands = await scan_handlers_for_commands()
        lines = [f"{cmd} → {desc}" for cmd, desc in sorted(commands.items())]
        text = "\n".join(lines) if lines else "Komut bulunamadı."
        await update.message.reply_text(f"<pre>{text}</pre>", parse_mode="HTML")
        return

    tree_text, valid_files = await format_tree(ROOT_DIR)

    if mode == "t":
        txt_filename = f"{TELEGRAM_NAME}_{timestamp}.txt"
        try:
            with open(txt_filename, 'w', encoding='utf-8') as out:
                for filepath in valid_files:
                    rel_path = os.path.relpath(filepath, ROOT_DIR)
                    separator = "=" * (len(rel_path) + 4)
                    out.write(f"\n{separator}\n")
                    out.write(f"|| {rel_path} ||\n")
                    out.write(f"{separator}\n\n")
                    try:
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                            out.write(f.read())
                    except Exception as e:
                        out.write(f"<HATA: {e}>\n")
                    out.write("\n\n")
            with open(txt_filename, 'rb') as f:
                await update.message.reply_document(document=f, filename=txt_filename)
        except Exception as e:
            logger.exception("TXT dosyası oluşturulurken hata")
            await update.message.reply_text(f"Hata oluştu: {e}")
        finally:
            if os.path.exists(txt_filename):

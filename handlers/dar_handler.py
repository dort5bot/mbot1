"""
handlers/dar_handler.py

/dar      → Dosya ağacı (mesaj, uzun olursa TXT gönderir)
/dar z    → ZIP (tree.txt + içerikler, sadece listelenen dosyalar + .env + .gitignore)
/dar k    → Alfabetik komut listesi (+ açıklamalar)
/dar t    → Projedeki tüm geçerli dosyaların içeriği tek bir .txt dosyada

Aiogram 
"""
"""
handlers/dar_handler.py
"""

import os
import re
import zipfile
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

# Load environment
load_dotenv()
TELEGRAM_NAME: str = os.getenv("TELEGRAM_NAME", "xbot")

# Constants
ROOT_DIR = Path(".").resolve()
TELEGRAM_MSG_LIMIT = 4000
HANDLERS_DIR = ROOT_DIR / "handlers"

logger = logging.getLogger(__name__)

# COMMAND INFO
COMMAND_INFO: Dict[str, str] = {
    "dar": "/dar: Dosya tree, /dar k: komut listesi, /dar z:repo zip, /dar t: tüm içerik txt",
    "io": "In-Out Alış Satış Baskısı raporu",
    "nls": "Balina hareketleri ve yoğunluk (NLS analizi)",
    "npr": "Nakit Piyasa Raporu",
    "eft": "ETF & ABD piyasaları",
    "ap": "Altların Güç Endeksi (AP)",
    "p": "/p liste, /p n :hacimli n coin, /p coin1...: sorgu Anlıkfiyat+24hdeğişim+hacim",
    # ... diğer komutlar
}

class DarService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            self.root_dir = ROOT_DIR
            self.handlers_dir = HANDLERS_DIR
            self.initialized = True

    def format_tree(self) -> Tuple[str, List[Path]]:
        tree_lines = []
        valid_files = []

        def walk(dir_path, prefix=""):
            try:
                items = sorted([p.name for p in dir_path.iterdir()])
            except Exception:
                return

            for i, item in enumerate(items):
                path = dir_path / item
                connector = "└── " if i == len(items) - 1 else "├── "

                if path.is_dir():
                    if item.startswith("__") or (item.startswith(".") and item not in [".gitignore", ".env"]):
                        continue
                    tree_lines.append(f"{prefix}{connector}{item}/")
                    walk(path, prefix + ("    " if i == len(items) - 1 else "│   "))
                else:
                    tree_lines.append(f"{prefix}{connector}{item}")
                    valid_files.append(path)

        walk(self.root_dir)
        return "\n".join(tree_lines), valid_files

    def scan_handlers_for_commands(self) -> Dict[str, str]:
        commands = {}
        handler_pattern = re.compile(r'CommandHandler\(\s*[\'"]/?(\w+)[\'"]', re.IGNORECASE)

        if not self.handlers_dir.exists():
            return commands

        for fname in os.listdir(self.handlers_dir):
            if not fname.endswith("_handler.py"):
                continue
            fpath = self.handlers_dir / fname
            try:
                content = fpath.read_text(encoding="utf-8")
            except Exception:
                continue
            
            matches = handler_pattern.findall(content)
            for cmd in matches:
                desc = COMMAND_INFO.get(cmd.lower(), "(açıklama yok)")
                commands[f"/{cmd}"] = f"{desc} ({fname})"

        return commands

    def create_zip(self, tree_text: str, valid_files: List[Path]) -> Path:
        timestamp = datetime.now().strftime("%m%d_%H%M")
        zip_filename = Path(f"{TELEGRAM_NAME}_{timestamp}.zip")

        with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr("tree.txt", tree_text)
            for fpath in valid_files:
                try:
                    zipf.write(fpath, fpath.relative_to(self.root_dir))
                except Exception:
                    continue
            for extra in [".env", ".gitignore"]:
                extra_path = self.root_dir / extra
                if extra_path.exists():
                    zipf.write(extra_path, extra)

        return zip_filename

    def create_all_txt(self, valid_files: List[Path]) -> Path:
        timestamp = datetime.now().strftime("%m%d_%H%M")
        txt_filename = Path(f"{TELEGRAM_NAME}_all_{timestamp}.txt")

        with txt_filename.open("w", encoding="utf-8") as f:
            for fpath in valid_files:
                try:
                    content = fpath.read_text(encoding="utf-8")
                except Exception:
                    continue
                f.write(f"\n\n===== {fpath} =====\n\n")
                f.write(content)

        return txt_filename

def get_dar_service():
    return DarService()

async def dar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    service = get_dar_service()
    args = context.args or []
    mode = args[0].lower() if args else ""

    tree_text, valid_files = service.format_tree()

    if mode == "k":
        scanned = service.scan_handlers_for_commands()
        if not scanned:
            await update.message.reply_text("Komut bulunamadı.")
            return
        lines = [f"{cmd} → {desc}" for cmd, desc in sorted(scanned.items())]
        text = "\n".join(lines)
        await update.message.reply_text(f"<pre>{text}</pre>", parse_mode=ParseMode.HTML)
        return

    if mode == "z":
        zip_path = service.create_zip(tree_text, valid_files)
        try:
            await update.message.reply_document(document=open(zip_path, "rb"), filename=zip_path.name)
        finally:
            zip_path.unlink(missing_ok=True)
        return

    if mode == "t":
        txt_path = service.create_all_txt(valid_files)
        try:
            await update.message.reply_document(document=open(txt_path, "rb"), filename=txt_path.name)
        finally:
            txt_path.unlink(missing_ok=True)
        return

    # default: dosya ağacı
    if len(tree_text) > TELEGRAM_MSG_LIMIT:
        timestamp = datetime.now().strftime("%m%d_%H%M")
        txt_filename = Path(f"{TELEGRAM_NAME}_{timestamp}.txt")
        txt_filename.write_text(tree_text, encoding="utf-8")
        try:
            await update.message.reply_document(document=open(txt_filename, "rb"), filename=txt_filename.name)
        finally:
            txt_filename.unlink(missing_ok=True)
    else:
        await update.message.reply_text(f"<pre>{tree_text}</pre>", parse_mode=ParseMode.HTML)

def register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("dar", dar_command))
    logger.info("✅ /dar handler yüklendi")

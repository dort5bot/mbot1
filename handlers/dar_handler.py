"""
handlers/dar_handler.py

/dar      → Dosya ağacı (mesaj, uzun olursa TXT gönderir)
/dar Z    → ZIP (tree.txt + içerikler, sadece listelenen dosyalar + .env + .gitignore)
/dar k    → Alfabetik komut listesi (+ açıklamalar)
/dar t    → Projedeki tüm geçerli dosyaların içeriği tek bir .txt dosyada

Tamamen async uyumlu + PEP8 + type hints + singleton + logging destekli.
"""

from __future__ import annotations

import os
import re
import zipfile
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# Load environment
load_dotenv()
TELEGRAM_NAME: str = os.getenv("TELEGRAM_NAME", "xbot")

# Constants
ROOT_DIR = Path(".").resolve()
TELEGRAM_MSG_LIMIT = 4000
HANDLERS_DIR = ROOT_DIR / "handlers"

LOG: logging.Logger = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)

# COMMAND INFO
COMMAND_INFO: Dict[str, str] = {
    "dar": "/dar: Dosya tree, /dar k: komut listesi, /dar z:repo zip",
    "io": "In-Out Alış Satış Baskısı raporu",
    "nls": "Balina hareketleri ve yoğunluk (NLS analizi)",
    "npr": "Nakit Piyasa Raporu",
    "eft": "ETF & ABD piyasaları",
    "ap": "Altların Güç Endeksi (AP)",
    "p": "/p liste, /p n :hacimli n coin, /p coin1...: sorgu Anlıkfiyat+24hdeğişim+hacim",
    "p_ekle": "Favori coin listesine coin ekler",
    "p_fav": "Favori coin listesini gösterir",
    "p_sil": "Favori coin listesinden coin siler",
    "fr": "Funding Rate raporu ve günlük CSV kaydı",
    "whale": "Whale Alerts raporu ve günlük CSV kaydı",
    "t": "/t →hazir liste, /t n →hacimli n coin, /t coin zaman →coin zaman bilgisi",
    "etf": "wobot2 etf  → yok",
    "komut": "tınak_içi_açıklama_ sonrasında VİRGÜL",
}


class DarService:
    """
    Singleton servis: proje dosya ağacını tarar, komut listesini tarar,
    ZIP / TXT oluşturma işlemlerini yönetir.
    """

    _instance: Optional["DarService"] = None

    def __new__(cls) -> "DarService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            LOG.debug("DarService: yeni örnek oluşturuldu")
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "initialized"):
            self.root_dir: Path = ROOT_DIR
            self.handlers_dir: Path = HANDLERS_DIR
            self.initialized = True
            LOG.debug("DarService: başlatıldı (singleton)")

    def format_tree(self) -> Tuple[str, List[Path]]:
        tree_lines: List[str] = []
        valid_files: List[Path] = []

        def walk(dir_path: Path, prefix: str = "") -> None:
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
        commands: Dict[str, str] = {}
        handler_pattern = re.compile(r'CommandHandler\(\s*[\'"]/?(\w+)[\'"]', flags=re.IGNORECASE)

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


def get_dar_service() -> DarService:
    return DarService()


async def dar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    service = get_dar_service()
    args: List[str] = context.args or []
    mode = args[0].lower() if args else ""

    if mode == "k":
        scanned = service.scan_handlers_for_commands()
        if not scanned:
            await update.message.reply_text("Komut bulunamadı.")
            return
        lines = [f"{cmd} → {desc}" for cmd, desc in sorted(scanned.items())]
        text = "\n".join(lines)
        await update.message.reply_text(f"<pre>{text}</pre>", parse_mode="HTML")
        return

    tree_text, _ = service.format_tree()
    if len(tree_text) > TELEGRAM_MSG_LIMIT:
        timestamp = datetime.now().strftime("%m%d_%H%M")
        txt_filename = Path(f"{TELEGRAM_NAME}_{timestamp}.txt")
        txt_filename.write_text(tree_text, encoding="utf-8")
        with txt_filename.open("rb") as f:
            await update.message.reply_document(document=f, filename=txt_filename.name)
        txt_filename.unlink(missing_ok=True)
        return

    await update.message.reply_text(f"<pre>{tree_text}</pre>", parse_mode="HTML")


# 🔑 Loader ile tam uyumlu hale getirildi
async def register(app: Application) -> None:
    """
    Application nesnesine /dar handler ekler.
    Loader bu fonksiyonu await edebilir.
    """
    app.add_handler(CommandHandler("dar", dar_command))
    LOG.info("🟢 /dar handler yüklendi")

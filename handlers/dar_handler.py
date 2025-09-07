"""
handlers/dar_handler.py

/dar      → Dosya ağacı (mesaj, uzun olursa TXT gönderir)
/dar z    → ZIP (tree.txt + içerikler, sadece listelenen dosyalar + .env + .gitignore)
/dar k    → Alfabetik komut listesi (+ açıklamalar)
/dar t    → Projedeki tüm geçerli dosyaların içeriği tek bir .txt dosyada

Aiogram 3.x uyumlu, async/await pattern'ine uygun hale getirilmiştir.
"""

import os
import re
import zipfile
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from dotenv import load_dotenv
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import FSInputFile

# Load environment
load_dotenv()
TELEGRAM_NAME: str = os.getenv("TELEGRAM_NAME", "xbot")

# Constants
ROOT_DIR = Path(".").resolve()
TELEGRAM_MSG_LIMIT = 4000
HANDLERS_DIR = ROOT_DIR / "handlers"

logger = logging.getLogger(__name__)
router = Router(name="dar_handler")

# COMMAND INFO
COMMAND_INFO: Dict[str, str] = {
    "dar": "/dar: Dosya tree, /dar k: komut listesi, /dar z:repo zip, /dar t: tüm içerik txt",
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
            logger.debug("DarService: yeni örnek oluşturuldu")
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "initialized"):
            self.root_dir: Path = ROOT_DIR
            self.handlers_dir: Path = HANDLERS_DIR
            self.initialized = True
            logger.debug("DarService: başlatıldı (singleton)")

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
        router_pattern = re.compile(r'router\.(message|callback_query)\(\s*Command\(\s*[\'"](\w+)[\'"]', flags=re.IGNORECASE)

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
            
            # Eski CommandHandler pattern
            matches = handler_pattern.findall(content)
            for cmd in matches:
                desc = COMMAND_INFO.get(cmd.lower(), "(açıklama yok)")
                commands[f"/{cmd}"] = f"{desc} ({fname})"
            
            # Yeni Router pattern
            router_matches = router_pattern.findall(content)
            for _, cmd in router_matches:
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

            # özel dosyalar
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


def get_dar_service() -> DarService:
    return DarService()


@router.message(Command("dar"))
async def dar_command(message: types.Message) -> None:
    """Handle /dar command with various modes"""
    service = get_dar_service()
    args = message.text.split()[1:] if message.text else []
    mode = args[0].lower() if args else ""

    tree_text, valid_files = service.format_tree()

    if mode == "k":
        scanned = service.scan_handlers_for_commands()
        if not scanned:
            await message.reply("Komut bulunamadı.")
            return
        lines = [f"{cmd} → {desc}" for cmd, desc in sorted(scanned.items())]
        text = "\n".join(lines)
        await message.reply(f"<pre>{text}</pre>", parse_mode="HTML")
        return

    if mode == "z":
        zip_path = service.create_zip(tree_text, valid_files)
        try:
            document = FSInputFile(zip_path)
            await message.reply_document(document=document, filename=zip_path.name)
        finally:
            zip_path.unlink(missing_ok=True)
        return

    if mode == "t":
        txt_path = service.create_all_txt(valid_files)
        try:
            document = FSInputFile(txt_path)
            await message.reply_document(document=document, filename=txt_path.name)
        finally:
            txt_path.unlink(missing_ok=True)
        return

    # default: sadece dosya ağacı
    if len(tree_text) > TELEGRAM_MSG_LIMIT:
        timestamp = datetime.now().strftime("%m%d_%H%M")
        txt_filename = Path(f"{TELEGRAM_NAME}_{timestamp}.txt")
        txt_filename.write_text(tree_text, encoding="utf-8")
        try:
            document = FSInputFile(txt_filename)
            await message.reply_document(document=document, filename=txt_filename.name)
        finally:
            txt_filename.unlink(missing_ok=True)
    else:
        await message.reply_text(f"<pre>{tree_text}</pre>", parse_mode="HTML")


def register_handlers(application: Any) -> None:
    """Register /dar handler to application"""
    application.add_handler(router)
    logger.info("✅ /dar handler yüklendi")

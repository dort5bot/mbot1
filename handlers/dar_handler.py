#dar_handler.py
from __future__ import annotations

import os
import re
import zipfile
import logging
import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from aiogram import Router
from aiogram.types import Message, InputFile
from aiogram.filters import Command

# Load environment
load_dotenv()
TELEGRAM_NAME: str = os.getenv("TELEGRAM_NAME", "xbot")

# Constants
ROOT_DIR = Path(".").resolve()
TELEGRAM_MSG_LIMIT = 4000
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
HANDLERS_DIR = ROOT_DIR / "handlers"
CACHE_DURATION = 30

# Geçici dosya yolu (Render vb. için güvenli dizin)
TEMP_DIR = Path(os.getenv("TEMP_DIR", "/tmp"))
TEMP_DIR.mkdir(parents=True, exist_ok=True)

LOG: logging.Logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Router
router = Router(name="dar_handler")

# Komut açıklamaları
COMMAND_INFO: Dict[str, str] = {
    "dar": "Dosya tree, komut listesi, repo zip, tüm içerik txt",
    "start": "Botu başlatır",
    "kay": "Mail adreslerini listeler",
    "kayek": "Mail adresi ekler",
    "kaysil": "Mail adresi siler",
    "gr": "Grupları listeler",
    "grek": "Yeni grup ekler",
    "grsil": "Grup siler",
    "checkmail": "Mail kontrolü yapar",
    "process": "Excel işler",
    "cleanup": "Temp temizler",
    "stats": "Bot istatistikleri",
    "proc": "Excel dosyalarını işler",
    "health": "Sağlık kontrolü",
    "ping": "Ping testi",
    "status": "Durum raporu",
    "gruplar": "Tüm grupları listeler",
}


class DarService:
    _instance: Optional["DarService"] = None

    def __new__(cls) -> "DarService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "initialized"):
            self.root_dir: Path = ROOT_DIR
            self.handlers_dir: Path = HANDLERS_DIR
            self.command_cache: Optional[Dict[str, str]] = None
            self.cache_time: Optional[float] = None
            self.initialized = True

    def format_tree(self) -> Tuple[str, List[Path]]:
        tree_lines: List[str] = []
        valid_files: List[Path] = []

        def walk(dir_path: Path, prefix: str = "") -> None:
            try:
                items = sorted([p.name for p in dir_path.iterdir()])
            except Exception as e:
                LOG.warning(f"Dizin okunamadı {dir_path}: {e}")
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

    def create_zip(self, tree_text: str, valid_files: List[Path]) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = TEMP_DIR / f"{TELEGRAM_NAME}_{timestamp}.zip"
        with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr("tree.txt", tree_text)
            for fpath in valid_files:
                try:
                    zipf.write(fpath, fpath.relative_to(self.root_dir))
                except Exception as e:
                    LOG.warning(f"Zip eklenemedi {fpath}: {e}")
            for extra in [".env", ".gitignore"]:
                extra_path = self.root_dir / extra
                if extra_path.exists():
                    zipf.write(extra_path, extra)
        return zip_filename

    def create_all_txt(self, valid_files: List[Path]) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        txt_filename = TEMP_DIR / f"{TELEGRAM_NAME}_all_{timestamp}.txt"
        with txt_filename.open("w", encoding="utf-8") as f:
            for fpath in valid_files:
                try:
                    content = fpath.read_text(encoding="utf-8")
                except Exception as e:
                    LOG.warning(f"{fpath} okunamadı: {e}")
                    continue
                f.write(f"\n\n{'='*50}\n{fpath}\n{'='*50}\n\n")
                f.write(content)
        return txt_filename


def get_dar_service() -> DarService:
    return DarService()


@router.message(Command("dar"))
async def handle_dar_command(message: Message) -> None:
    service = get_dar_service()
    args = message.text.split()[1:] if message.text else []
    mode = args[0].lower() if args else ""

    try:
        tree_text, valid_files = service.format_tree()

        if mode == "z":  # zip
            zip_path = service.create_zip(tree_text, valid_files)
            input_file = InputFile(zip_path, filename=zip_path.name)
            await message.answer_document(document=input_file)
            zip_path.unlink(missing_ok=True)
            return

        if mode == "t":  # all txt
            txt_path = service.create_all_txt(valid_files)
            input_file = InputFile(txt_path, filename=txt_path.name)
            await message.answer_document(document=input_file)
            txt_path.unlink(missing_ok=True)
            return

        # default tree
        if len(tree_text) > TELEGRAM_MSG_LIMIT:
            txt_filename = TEMP_DIR / f"{TELEGRAM_NAME}_tree.txt"
            txt_filename.write_text(tree_text, encoding="utf-8")
            input_file = InputFile(txt_filename, filename=txt_filename.name)
            await message.answer_document(document=input_file)
            txt_filename.unlink(missing_ok=True)
        else:
            await message.answer(f"<pre>{tree_text}</pre>", parse_mode="HTML")

    except Exception as e:
        LOG.error(f"Dar komutu hata: {e}")
        await message.answer(f"❌ Hata: {str(e)}")


async def register_handlers(router_instance: Router):
    router_instance.include_router(router)

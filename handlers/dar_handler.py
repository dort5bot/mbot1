"""
handlers/dar_handler.py

/dar      → Dosya ağacı (mesaj, uzun olursa TXT gönderir)
/dar z    → ZIP (tree.txt + içerikler, sadece listelenen dosyalar + .env + .gitignore)
/dar k    → Alfabetik komut listesi (+ açıklamalar)
/dar k f  →  önbelleği temizleme (Force Refresh)
/dar t    → Projedeki tüm geçerli dosyaların içeriği tek bir .txt dosyada

Tamamen async uyumlu + PEP8 + type hints + singleton + logging destekli.
Aiogram 3.x Router pattern uyumlu.
"""

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
from aiogram.types import Message
from aiogram.filters import Command

# Load environment
load_dotenv()
TELEGRAM_NAME: str = os.getenv("TELEGRAM_NAME", "xbot")

# Constants
ROOT_DIR = Path(".").resolve()
TELEGRAM_MSG_LIMIT = 4000
HANDLERS_DIR = ROOT_DIR / "handlers"
CACHE_DURATION = 30  # 30 saniye önbellekleme

LOG: logging.Logger = logging.getLogger(__name__)

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

# Router oluştur
dar_router = Router(name="dar_router")


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
            self.command_cache: Optional[Dict[str, str]] = None
            self.cache_time: Optional[float] = None
            self.initialized = True
            LOG.debug("DarService: başlatıldı (singleton)")

    def format_tree(self) -> Tuple[str, List[Path]]:
        """
        Dosya ağacını oluşturur ve geçerli dosyaları listeler.
        
        Returns:
            Tuple[str, List[Path]]: Ağaç metni ve geçerli dosya yolları
        """
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

    async def scan_handlers_for_commands(self, force_refresh: bool = False) -> Dict[str, str]:
        """
        Önbelleklenmiş komut listesi döndürür.
        
        Args:
            force_refresh: Önbelleği zorla yenile
            
        Returns:
            Dict[str, str]: Komut adı ve açıklamaları
        """
        # Önbellek kontrolü
        if (not force_refresh and self.command_cache and self.cache_time and 
            (time.time() - self.cache_time) < CACHE_DURATION):
            LOG.debug("Önbellekten komut listesi döndürülüyor")
            return self.command_cache
        
        # Önbellek yenileme
        self.command_cache = await self._scan_handlers()
        self.cache_time = time.time()
        return self.command_cache

    async def _scan_handlers(self) -> Dict[str, str]:
        """
        Handler dosyalarını tarayarak komut listesi oluşturur.
        
        Returns:
            Dict[str, str]: Komut adı ve açıklamaları içeren sözlük
        """
        commands: Dict[str, str] = {}
        
        # Kapsamlı regex pattern'leri
        patterns = [
            r'CommandHandler\(\s*[\'"]/?(\w+)[\'"]',  # CommandHandler("komut")
            r'@\w+\.message\(Command\([\'"](\w+)[\'"]\)',  # @router.message(Command("komut"))
            r'Command\([\'"](\w+)[\'"]\)',  # Command("komut")
            r'commands\s*=\s*\[[\'"](\w+)[\'"]',  # commands = ["komut"]
            r'command=[\'"](\w+)[\'"]',  # command="komut"
        ]
        
        if not self.handlers_dir.exists():
            LOG.error("Handlers dizini bulunamadı")
            return commands

        for fname in os.listdir(self.handlers_dir):
            if not fname.endswith("_handler.py"):
                continue
            fpath = self.handlers_dir / fname
            
            try:
                # Async dosya okuma
                content = await asyncio.to_thread(fpath.read_text, encoding="utf-8")
            except Exception as e:
                LOG.warning(f"{fname} okunamadı: {e}")
                continue
            
            # Tüm pattern'leri ara
            found_commands = set()
            for pattern in patterns:
                try:
                    matches = re.findall(pattern, content, flags=re.IGNORECASE)
                    found_commands.update(matches)
                except re.error as e:
                    LOG.warning(f"Regex hatası {pattern}: {e}")
            
            for cmd in found_commands:
                desc = COMMAND_INFO.get(cmd.lower(), "(açıklama yok)")
                commands[f"/{cmd}"] = f"{desc} ({fname})"
        
        LOG.info(f"{len(commands)} komut bulundu")
        return commands

    def create_zip(self, tree_text: str, valid_files: List[Path]) -> Path:
        """
        ZIP dosyası oluşturur.
        
        Args:
            tree_text: Dosya ağacı metni
            valid_files: Dahil edilecek dosya listesi
            
        Returns:
            Path: Oluşturulan ZIP dosyasının yolu
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = Path(f"{TELEGRAM_NAME}_{timestamp}.zip")

        try:
            with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
                zipf.writestr("tree.txt", tree_text)

                for fpath in valid_files:
                    try:
                        zipf.write(fpath, fpath.relative_to(self.root_dir))
                    except Exception as e:
                        LOG.warning(f"{fpath} ZIP'e eklenemedi: {e}")
                        continue

                # özel dosyalar
                for extra in [".env", ".gitignore"]:
                    extra_path = self.root_dir / extra
                    if extra_path.exists():
                        try:
                            zipf.write(extra_path, extra)
                        except Exception as e:
                            LOG.warning(f"{extra} ZIP'e eklenemedi: {e}")

            LOG.info(f"ZIP oluşturuldu: {zip_filename}")
            return zip_filename
            
        except Exception as e:
            LOG.error(f"ZIP oluşturma hatası: {e}")
            raise

    def create_all_txt(self, valid_files: List[Path]) -> Path:
        """
        Tüm dosya içeriklerini birleştirerek TXT dosyası oluşturur.
        
        Args:
            valid_files: Dahil edilecek dosya listesi
            
        Returns:
            Path: Oluşturulan TXT dosyasının yolu
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        txt_filename = Path(f"{TELEGRAM_NAME}_all_{timestamp}.txt")

        try:
            with txt_filename.open("w", encoding="utf-8") as f:
                for fpath in valid_files:
                    try:
                        content = fpath.read_text(encoding="utf-8")
                    except Exception as e:
                        LOG.warning(f"{fpath} okunamadı: {e}")
                        continue
                    f.write(f"\n\n{'='*50}\n{fpath}\n{'='*50}\n\n")
                    f.write(content)

            LOG.info(f"TXT oluşturuldu: {txt_filename}")
            return txt_filename
            
        except Exception as e:
            LOG.error(f"TXT oluşturma hatası: {e}")
            raise

    async def clear_cache(self) -> None:
        """Komut önbelleğini temizler."""
        self.command_cache = None
        self.cache_time = None
        LOG.info("Komut önbelleği temizlendi")


def get_dar_service() -> DarService:
    """DarService singleton örneğini döndürür."""
    return DarService()


@dar_router.message(Command("dar"))
async def dar_command(message: Message) -> None:
    """
    /dar komutunu işler: Dosya ağacı, ZIP, komut listesi veya tüm içerik TXT.
    
    Args:
        message: Gelen mesaj nesnesi
    """
    service = get_dar_service()
    
    # Komut argümanlarını al
    args = message.text.split()[1:] if message.text else []
    mode = args[0].lower() if args else ""
    force_refresh = "f" in args  # force refresh parametresi

    try:
        tree_text, valid_files = service.format_tree()

        if mode == "k":
            # Komut listesi modu
            scanned = await service.scan_handlers_for_commands(force_refresh=force_refresh)
            if not scanned:
                await message.answer("Komut bulunamadı.")
                return
            lines = [f"{cmd} → {desc}" for cmd, desc in sorted(scanned.items())]
            text = "\n".join(lines)
            
            if len(text) > TELEGRAM_MSG_LIMIT:
                # Uzunsa dosya olarak gönder
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                txt_filename = Path(f"{TELEGRAM_NAME}_commands_{timestamp}.txt")
                txt_filename.write_text(text, encoding="utf-8")
                await message.answer_document(
                    document=txt_filename.open("rb"),
                    filename=txt_filename.name
                )
                txt_filename.unlink(missing_ok=True)
            else:
                await message.answer(f"<pre>{text}</pre>", parse_mode="HTML")
            return

        if mode == "z":
            # ZIP modu
            zip_path = service.create_zip(tree_text, valid_files)
            await message.answer_document(
                document=zip_path.open("rb"),
                filename=zip_path.name
            )
            zip_path.unlink(missing_ok=True)
            return

        if mode == "t":
            # Tüm içerik TXT modu
            txt_path = service.create_all_txt(valid_files)
            await message.answer_document(
                document=txt_path.open("rb"),
                filename=txt_path.name
            )
            txt_path.unlink(missing_ok=True)
            return

        if mode == "f":
            # Force refresh
            await service.clear_cache()
            await message.answer("✅ Önbellek temizlendi. Tekrar deneyin.")
            return

        # Varsayılan: sadece dosya ağacı
        if len(tree_text) > TELEGRAM_MSG_LIMIT:
            # Mesaj sınırını aşıyorsa TXT dosyası olarak gönder
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            txt_filename = Path(f"{TELEGRAM_NAME}_{timestamp}.txt")
            txt_filename.write_text(tree_text, encoding="utf-8")
            await message.answer_document(
                document=txt_filename.open("rb"),
                filename=txt_filename.name
            )
            txt_filename.unlink(missing_ok=True)
        else:
            # Doğrudan mesaj olarak gönder
            await message.answer(f"<pre>{tree_text}</pre>", parse_mode="HTML")
            
    except Exception as e:
        LOG.error(f"/dar komutu hatası: {e}")
        await message.answer("❌ Bir hata oluştu. Lütfen daha sonra tekrar deneyin.")


async def register(router: Router) -> None:
    """
    Router'a /dar handler'ı ekler.
    
    Args:
        router: Aiogram Router nesnesi
    """
    router.include_router(dar_router)
    LOG.info("🟢 /dar handler yüklendi")

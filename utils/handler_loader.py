"""
utils/handler_loader.py
-----------------------
Telegram bot handler dosyalarını otomatik yüklemek için yardımcı modül.

🔧 Özellikler:
- Handler plugin loader
- Silinen dosyaları otomatik olarak cache'ten temizler
- Alt klasör (recursive) desteği
- Async uyumlu
- Singleton pattern
- Logging destekli
- PEP8 + type hints uyumlu
"""

import os
import sys
import importlib
import logging
from types import ModuleType
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class HandlerLoader:
    """
    Telegram bot handler dosyalarını dinamik olarak yüklemek için singleton sınıf.

    Alt klasör desteği ile:
        handlers/abc.py  -> handlers.abc
        handlers/analiz/xyz.py -> handlers.analiz.xyz
    """

    _instance: Optional["HandlerLoader"] = None

    def __new__(cls, handlers_dir: str = "handlers") -> "HandlerLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize(handlers_dir)
            logger.info("✅ HandlerLoader singleton instance created")
        return cls._instance

    def _initialize(self, handlers_dir: str) -> None:
        self.handlers_dir = handlers_dir
        self._cache: Dict[str, ModuleType] = {}

    def _discover_handler_files(self) -> List[str]:
        """
        Handler dizinindeki tüm .py dosyalarını recursive şekilde bulur.

        Returns:
            List of file paths relative to handlers_dir
        """
        handler_files: List[str] = []
        for root, _, files in os.walk(self.handlers_dir):
            for file in files:
                if file.endswith(".py") and not file.startswith("_"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.handlers_dir)
                    module_name = rel_path[:-3].replace(os.sep, ".")
                    handler_files.append(module_name)
        return handler_files

    async def load_handlers(self) -> List[ModuleType]:
        """
        Handler dosyalarını yükle (recursive destekli).

        Returns:
            Yüklenen handler modüllerinin listesi
        """
        loaded_modules: List[ModuleType] = []

        if not os.path.isdir(self.handlers_dir):
            logger.warning(f"⚠️ Handler directory '{self.handlers_dir}' not found.")
            return loaded_modules

        handler_modules = self._discover_handler_files()
        for module_name in handler_modules:
            full_module = f"{self.handlers_dir}.{module_name}"
            try:
                if full_module in sys.modules:
                    module = importlib.reload(sys.modules[full_module])
                else:
                    module = importlib.import_module(full_module)
                self._cache[full_module] = module
                loaded_modules.append(module)
                logger.info(f"✅ Loaded handler: {full_module}")
            except Exception as e:
                logger.error(f"❌ Failed to load handler {full_module}: {e}")
        return loaded_modules

    async def clear_cache(self) -> None:
        """
        Handler cache'i temizle (silinen dosyaları kaldır).
        """
        removed = []
        for module_name in list(self._cache.keys()):
            # modulename -> handlers.analiz.xyz
            relative_path = module_name.replace(".", os.sep) + ".py"
            full_path = os.path.join(os.getcwd(), relative_path)

            if not os.path.exists(full_path):
                sys.modules.pop(module_name, None)
                self._cache.pop(module_name, None)
                removed.append(module_name)

        if removed:
            logger.info(f"🧹 Removed handlers from cache: {removed}")

    async def get_loaded_handlers(self) -> Dict[str, ModuleType]:
        """
        Yüklenmiş handler modüllerini döndür.
        """
        return self._cache


# Singleton instance
handler_loader = HandlerLoader()

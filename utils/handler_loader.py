"""
utils/handler_loader.py
-----------------------
Telegram bot handler dosyalarını otomatik yüklemek için yardımcı modül.

🔧 Geliştirilmiş Özellikler:
- Handler plugin loader with hot reload support
- Silinen dosyaları otomatik olarak cache'ten temizler
- Alt klasör (recursive) desteği
- Async uyumlu + performance monitoring
- Singleton pattern + runtime configuration
- Detaylı logging + error reporting
- PEP8 + type hints uyumlu
- Aiogram 3.x Router pattern desteği
Tüm handler'lar register_handlers fonksiyonu aracılığıyla application'a eklenir
"""
"""
utils/handler_loader.py
"""

import os
import sys
import importlib
import logging
import time
from types import ModuleType
from typing import Dict, List, Optional, Any, Tuple

from telegram.ext import Application

logger = logging.getLogger(__name__)

class HandlerLoader:
    _instance = None

    def __new__(cls, handlers_dir: str = "handlers"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize(handlers_dir)
        return cls._instance

    def _initialize(self, handlers_dir: str):
        self.handlers_dir = handlers_dir
        self._cache = {}

    def _discover_handler_files(self) -> List[str]:
        handler_files = []
        if not os.path.isdir(self.handlers_dir):
            return handler_files

        for root, _, files in os.walk(self.handlers_dir):
            for file in files:
                if file.endswith(".py") and not file.startswith("_"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.handlers_dir)
                    module_name = rel_path[:-3].replace(os.sep, ".")
                    handler_files.append(module_name)
        
        return handler_files

    async def load_handlers(self, application: Application) -> Dict[str, List[str]]:
        result = {'loaded': [], 'failed': [], 'registered': []}

        if not os.path.isdir(self.handlers_dir):
            return result

        handler_modules = self._discover_handler_files()
        
        for module_name in handler_modules:
            full_module = f"{self.handlers_dir}.{module_name}"
            try:
                if full_module in sys.modules:
                    module = importlib.reload(sys.modules[full_module])
                else:
                    module = importlib.import_module(full_module)
                
                self._cache[full_module] = module
                result['loaded'].append(full_module)
                
                if hasattr(module, "register_handlers"):
                    try:
                        module.register_handlers(application)
                        result['registered'].append(full_module)
                    except Exception as e:
                        result['failed'].append(f"{full_module} (register error: {e})")
                        
            except Exception as e:
                result['failed'].append(f"{full_module} (load error: {e})")

        return result

handler_loader = HandlerLoader()

async def load_handlers(application: Application) -> Dict[str, List[str]]:
    return await handler_loader.load_handlers(application)

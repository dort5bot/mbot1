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
            logger.info("✅ HandlerLoader singleton instance created")
        return cls._instance

    def _initialize(self, handlers_dir: str):
        self.handlers_dir = handlers_dir
        self._cache: Dict[str, ModuleType] = {}
        logger.info(f"📁 Handler directory set to: {handlers_dir}")

    def set_handlers_dir(self, handlers_dir: str) -> None:
        self.handlers_dir = handlers_dir
        self._cache.clear()
        logger.info(f"🔄 Handler directory changed to: {handlers_dir}")

    def _discover_handler_files(self) -> List[str]:
        handler_files: List[str] = []
        if not os.path.isdir(self.handlers_dir):
            logger.warning(f"⚠️ Handler directory '{self.handlers_dir}' not found.")
            return handler_files

        for root, _, files in os.walk(self.handlers_dir):
            for file in files:
                if file.endswith(".py") and not file.startswith("_"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.handlers_dir)
                    module_name = rel_path[:-3].replace(os.sep, ".")
                    handler_files.append(module_name)
        
        logger.info(f"🔍 Found {len(handler_files)} handler files")
        return handler_files

    async def load_handlers(self, application: Application) -> Dict[str, List[str]]:
        start_time = time.time()
        result = {'loaded': [], 'failed': [], 'registered': []}

        if not os.path.isdir(self.handlers_dir):
            logger.warning(f"⚠️ Handler directory '{self.handlers_dir}' not found.")
            return result

        handler_modules = self._discover_handler_files()
        
        for module_name in handler_modules:
            full_module = f"{self.handlers_dir}.{module_name}"
            try:
                if full_module in sys.modules:
                    module = importlib.reload(sys.modules[full_module])
                    logger.debug(f"🔄 Reloaded handler: {full_module}")
                else:
                    module = importlib.import_module(full_module)
                    logger.debug(f"📦 Imported handler: {full_module}")
                
                self._cache[full_module] = module
                result['loaded'].append(full_module)
                logger.info(f"✅ Loaded handler: {full_module}")
                
                if hasattr(module, "register_handlers"):
                    try:
                        module.register_handlers(application)
                        result['registered'].append(full_module)
                        logger.info(f"🔗 Registered handlers from {module.__name__}")
                    except Exception as e:
                        logger.error(f"❌ Failed to register handlers from {module.__name__}: {e}")
                        result['failed'].append(f"{full_module} (register error: {e})")
                        
            except Exception as e:
                logger.error(f"❌ Failed to load handler {full_module}: {e}")
                result['failed'].append(f"{full_module} (load error: {e})")

        end_time = time.time()
        logger.info(f"⏱️ Handler loading completed in {end_time - start_time:.2f} seconds")
        logger.info(f"📊 Results: {len(result['loaded'])} loaded, {len(result['registered'])} registered, {len(result['failed'])} failed")
        
        return result

    async def reload_handler(self, module_name: str, application: Optional[Application] = None) -> Tuple[bool, str]:
        try:
            full_module = f"{self.handlers_dir}.{module_name}"
            
            if full_module in sys.modules:
                module = importlib.reload(sys.modules[full_module])
                logger.info(f"🔄 Reloaded handler: {full_module}")
            else:
                module = importlib.import_module(full_module)
                logger.info(f"📦 Imported handler: {full_module}")
            
            self._cache[full_module] = module

            if application and hasattr(module, "register_handlers"):
                try:
                    module.register_handlers(application)
                    logger.info(f"🔗 Re-registered handlers from {module.__name__}")
                    return True, f"Handler {full_module} reloaded and re-registered successfully"
                except Exception as e:
                    error_msg = f"Handler {full_module} reloaded but registration failed: {e}"
                    logger.error(f"❌ {error_msg}")
                    return False, error_msg
            
            return True, f"Handler {full_module} reloaded successfully"
            
        except Exception as e:
            error_msg = f"Failed to reload handler {module_name}: {e}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg

    async def clear_cache(self) -> Dict[str, List[str]]:
        result = {'removed': [], 'remaining': list(self._cache.keys())}
        
        for module_name in list(self._cache.keys()):
            relative_path = module_name.replace(".", os.sep) + ".py"
            full_path = os.path.join(os.getcwd(), relative_path)

            if not os.path.exists(full_path):
                sys.modules.pop(module_name, None)
                self._cache.pop(module_name, None)
                result['removed'].append(module_name)
                result['remaining'].remove(module_name)

        if result['removed']:
            logger.info(f"🧹 Removed {len(result['removed'])} handlers from cache: {result['removed']}")
        
        return result

    async def get_loaded_handlers(self) -> Dict[str, ModuleType]:
        return self._cache

    def get_handler_count(self) -> int:
        return len(self._cache)


# Singleton instance
handler_loader = HandlerLoader()

# ---------------------------------------------------------------------
# Public async wrapper functions
# ---------------------------------------------------------------------
async def load_handlers(application: Application) -> Dict[str, List[str]]:
    return await handler_loader.load_handlers(application)

async def reload_handler(module_name: str, application: Optional[Application] = None) -> Tuple[bool, str]:
    return await handler_loader.reload_handler(module_name, application)

async def clear_handler_cache() -> Dict[str, List[str]]:
    return await handler_loader.clear_cache()

async def get_handler_status() -> Dict[str, Any]:
    handlers = await handler_loader.get_loaded_handlers()
    return {
        'total_handlers': len(handlers),
        'loaded_handlers': list(handlers.keys())
    }

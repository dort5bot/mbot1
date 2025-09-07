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
"""

import os
import sys
import importlib
import logging
import time
import inspect
from types import ModuleType
from typing import Dict, List, Optional, Any, Tuple

from aiogram import Router

logger = logging.getLogger(__name__)


class HandlerLoader:
    """
    Telegram bot handler dosyalarını dinamik olarak yüklemek için singleton sınıf.
    Geliştirilmiş özelliklerle: hot reload, performance monitoring, detailed reporting.
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
        self._routers: Dict[str, Router] = {}
        logger.info(f"📁 Handler directory set to: {handlers_dir}")

    def set_handlers_dir(self, handlers_dir: str) -> None:
        """Runtime'da handlers directory değiştirmek için"""
        self.handlers_dir = handlers_dir
        self._cache.clear()
        self._routers.clear()
        logger.info(f"🔄 Handler directory changed to: {handlers_dir}")

    def _discover_handler_files(self) -> List[str]:
        """
        Handler dizinindeki tüm .py dosyalarını recursive şekilde bulur.
        Returns:
            List of file paths relative to handlers_dir
        """
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

    async def load_handlers(self, application: Optional[Any] = None, main_router: Optional[Router] = None) -> Dict[str, List[str]]:
        """
        Handler dosyalarını yükle ve isteğe bağlı olarak kaydet.
        Returns:
            {'loaded': [], 'failed': [], 'registered': []}
        """
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
                
                # Eğer Application ve Router nesnesi verilirse handler'ları kaydet
                if application and main_router and hasattr(module, "register_handlers"):
                    try:
                        module.register_handlers(main_router)
                        result['registered'].append(full_module)
                        logger.info(f"🔗 Registered handlers from {module.__name__}")
                    except Exception as e:
                        logger.error(f"❌ Failed to register handlers from {module.__name__}: {e}")
                        result['failed'].append(f"{full_module} (register error: {e})")
                
                # Router'ı bul ve kaydet
                router = self._find_router_in_module(module)
                if router:
                    self._routers[full_module] = router
                    logger.info(f"📋 Found router in {module.__name__}: {router.name}")
                        
            except Exception as e:
                logger.error(f"❌ Failed to load handler {full_module}: {e}")
                result['failed'].append(f"{full_module} (load error: {e})")

        end_time = time.time()
        logger.info(f"⏱️ Handler loading completed in {end_time - start_time:.2f} seconds")
        logger.info(f"📊 Results: {len(result['loaded'])} loaded, {len(result['registered'])} registered, {len(result['failed'])} failed")
        
        return result

    def _find_router_in_module(self, module: ModuleType) -> Optional[Router]:
        """Module içinde Router nesnesi bul"""
        for name, obj in inspect.getmembers(module):
            if isinstance(obj, Router):
                return obj
        return None

    async def reload_handler(self, module_name: str, application: Optional[Any] = None, main_router: Optional[Router] = None) -> Tuple[bool, str]:
        """
        Belirli bir handler'ı yeniden yükler.
        Returns: (success: bool, message: str)
        """
        try:
            full_module = f"{self.handlers_dir}.{module_name}"
            
            if full_module in sys.modules:
                module = importlib.reload(sys.modules[full_module])
                logger.info(f"🔄 Reloaded handler: {full_module}")
            else:
                module = importlib.import_module(full_module)
                logger.info(f"📦 Imported handler: {full_module}")
            
            self._cache[full_module] = module

            # Router'ı güncelle
            router = self._find_router_in_module(module)
            if router:
                self._routers[full_module] = router
                logger.info(f"📋 Updated router in {module.__name__}: {router.name}")

            # Eğer Application ve Router nesnesi verilirse handler'ları yeniden kaydet
            if application and main_router and hasattr(module, "register_handlers"):
                try:
                    module.register_handlers(main_router)
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
        """
        Handler cache'i temizle (silinen dosyaları kaldır).
        Returns: {'removed': [], 'remaining': []}
        """
        result = {'removed': [], 'remaining': list(self._cache.keys())}
        
        for module_name in list(self._cache.keys()):
            relative_path = module_name.replace(".", os.sep) + ".py"
            full_path = os.path.join(os.getcwd(), relative_path)

            if not os.path.exists(full_path):
                sys.modules.pop(module_name, None)
                self._cache.pop(module_name, None)
                self._routers.pop(module_name, None)
                result['removed'].append(module_name)
                result['remaining'].remove(module_name)

        if result['removed']:
            logger.info(f"🧹 Removed {len(result['removed'])} handlers from cache: {result['removed']}")
        
        return result

    async def get_loaded_handlers(self) -> Dict[str, ModuleType]:
        """Yüklenmiş handler modüllerini döndür."""
        return self._cache

    def get_loaded_routers(self) -> Dict[str, Router]:
        """Yüklenmiş router'ları döndür."""
        return self._routers

    def get_handler_count(self) -> int:
        """Yüklenmiş handler sayısını döndür."""
        return len(self._cache)


# Singleton instance
handler_loader = HandlerLoader()

# ---------------------------------------------------------------------
# Public async wrapper functions
# ---------------------------------------------------------------------
async def load_handlers(application: Optional[Any] = None, main_router: Optional[Router] = None) -> Dict[str, List[str]]:
    """
    Public wrapper: Handler dosyalarını yükle.
    Returns: {'loaded': [], 'failed': [], 'registered': []}
    """
    return await handler_loader.load_handlers(application, main_router)


async def reload_handler(module_name: str, application: Optional[Any] = None, main_router: Optional[Router] = None) -> Tuple[bool, str]:
    """
    Public wrapper: Belirli bir handler'ı yeniden yükler.
    Returns: (success: bool, message: str)
    """
    return await handler_loader.reload_handler(module_name, application, main_router)


async def clear_handler_cache() -> Dict[str, List[str]]:
    """
    Public wrapper: Handler cache temizle.
    Returns: {'removed': [], 'remaining': []}
    """
    return await handler_loader.clear_cache()


async def get_handler_status() -> Dict[str, Any]:
    """
    Handler durum raporu döndür.
    Returns: {'total_handlers': int, 'loaded_handlers': List[str]}
    """
    handlers = await handler_loader.get_loaded_handlers()
    routers = handler_loader.get_loaded_routers()
    
    return {
        'total_handlers': len(handlers),
        'loaded_handlers': list(handlers.keys()),
        'total_routers': len(routers),
        'loaded_routers': list(routers.keys())
    }

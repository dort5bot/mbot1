# utils/handler_loader.py
import importlib
import pkgutil
import logging
from aiogram import Dispatcher

logger = logging.getLogger(__name__)

async def load_handlers(dispatcher: Dispatcher) -> dict:
    """handlers klasöründeki tüm modülleri yükler ve router'a ekler"""
    results = {"loaded": 0, "failed": 0}

    try:
        import handlers  # handlers klasörü package olmalı (__init__.py)
    except ImportError as e:
        logger.error(f"❌ Handlers package yüklenemedi: {e}")
        return results
    
    # Tüm handler modüllerini senkron olarak import et
    for _, module_name, is_pkg in pkgutil.iter_modules(handlers.__path__):
        if is_pkg:
            continue
        try:
            # Senkron import işlemi - await YOK!
            module = importlib.import_module(f"handlers.{module_name}")
            
            if hasattr(module, "router"):
                dispatcher.include_router(module.router)
                results["loaded"] += 1
                logger.info(f"✅ Handler yüklendi: {module_name}")
            else:
                results["failed"] += 1
                logger.warning(f"⚠️ Router bulunamadı: {module_name}")
                
        except ImportError as e:
            results["failed"] += 1
            logger.error(f"❌ Handler import edilemedi: {module_name} - {e}")
        except Exception as e:
            results["failed"] += 1
            logger.error(f"❌ Handler yüklenirken hata: {module_name} - {e}")

    logger.info(f"📊 Handler yükleme sonucu: {results['loaded']} başarılı, {results['failed']} başarısız")
    return results


async def clear_handler_cache():
    """Reload için cache temizleme"""
    import sys
    modules_to_remove = []
    
    for key in list(sys.modules.keys()):
        if key.startswith("handlers."):
            modules_to_remove.append(key)
    
    for module_name in modules_to_remove:
        try:
            del sys.modules[module_name]
            logger.debug(f"🧹 Cache temizlendi: {module_name}")
        except Exception as e:
            logger.warning(f"⚠️ Cache temizlenemedi {module_name}: {e}")
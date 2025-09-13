# utils/handler_loader.py
import importlib
import pkgutil
import logging
from pathlib import Path
from aiogram import Dispatcher

logger = logging.getLogger(__name__)

async def load_handlers(dispatcher: Dispatcher) -> dict:
    """handlers klasöründeki tüm modülleri yükler ve router'a ekler"""
    results = {"loaded": 0, "failed": 0}

    handlers_dir = Path("handlers")
    
    if not handlers_dir.exists():
        logger.error(f"❌ Handlers directory not found: {handlers_dir}")
        return results
    
    # Tüm handler dosyalarını tara
    for file_path in handlers_dir.glob("*.py"):
        if file_path.name == "__init__.py":
            continue
            
        module_name = file_path.stem
        try:
            # Modülü import et
            spec = importlib.util.spec_from_file_location(f"handlers.{module_name}", file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if hasattr(module, "router"):
                dispatcher.include_router(module.router)
                results["loaded"] += 1
                logger.info(f"✅ Handler yüklendi: {module_name}")
            else:
                results["failed"] += 1
                logger.warning(f"⚠️ Router bulunamadı: {module_name}")
                
        except Exception as e:
            results["failed"] += 1
            logger.error(f"❌ Handler yüklenirken hata: {module_name} - {e}")

    logger.info(f"📊 Handler yükleme sonucu: {results['loaded']} başarılı, {results['failed']} başarısız")
    return results

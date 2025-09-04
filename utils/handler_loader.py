"""
# Handler Loader
---------------
Telegram bot handler dosyalarını otomatik yüklemek için yardımcı modül.
Silinen dosyaları otomatik olarak cache'ten temizler.
"""

import os
import importlib
import logging
from types import ModuleType
from typing import Any, Callable, Optional, Set

LOG: logging.Logger = logging.getLogger("handler_loader")

# Singleton cache: Aynı handler iki kez yüklenmesin
_LOADED_HANDLERS: Set[str] = set()


async def load_handlers(application: Any, path: str = "handlers") -> None:
    """
    Belirtilen klasördeki tüm handler modüllerini tarar ve yükler.
    Silinen dosyaları cache'ten otomatik olarak temizler.
    Eğer modül içinde `register(application)` fonksiyonu varsa çağırır.

    Args:
        application (Any): Telegram Application instance.
        path (str, optional): Handler modüllerinin bulunduğu klasör. Default "handlers".

    Raises:
        ImportError: Bir modül yüklenemezse hata loglanır.
        AttributeError: Modülde register fonksiyonu yoksa hata loglanır.
    """
    global _LOADED_HANDLERS

    if not os.path.isdir(path):
        LOG.error(f"Handler path not found: {path}")
        return

    # Mevcut dosyaları bul
    current_files = {
        f"{path}.{file[:-3]}" for file in os.listdir(path) 
        if file.endswith(".py") and file != "__init__.py"
    }
    
    # Cache'i temizle (silinen dosyaları kaldır)
    _LOADED_HANDLERS = _LOADED_HANDLERS.intersection(current_files)
    
    for module_name in current_files:
        # Zaten yüklendiyse atla
        if module_name in _LOADED_HANDLERS:
            LOG.debug(f"Handler already loaded, skipping: {module_name}")
            continue

        try:
            module: ModuleType = importlib.import_module(module_name)

            register_func: Optional[Callable[[Any], Any]] = getattr(
                module, "register", None
            )
            if register_func is None:
                LOG.warning(f"No register() found in handler: {module_name}")
                continue

            # Eğer register async ise await et
            if callable(register_func):
                result = register_func(application)
                if hasattr(result, "__await__"):
                    await result
                LOG.info(f"Handler loaded: {module_name}")
                _LOADED_HANDLERS.add(module_name)
            else:
                LOG.warning(f"Invalid register in {module_name}, skipping.")

        except ImportError as exc:
            LOG.error(f"Import failed for handler {module_name}: {exc}")
        except AttributeError as exc:
            LOG.error(f"Attribute error in handler {module_name}: {exc}")
        except Exception as exc:
            LOG.exception(f"Failed to load handler {module_name}: {exc}")


def clear_handler_cache() -> None:
    """
    Handler cache'ini temizler. 
    Tüm handler'ların yeniden yüklenmesini sağlar.
    """
    global _LOADED_HANDLERS
    _LOADED_HANDLERS.clear()
    LOG.info("Handler cache cleared")


def get_loaded_handlers() -> Set[str]:
    """
    Yüklenmiş handler'ların listesini döndürür.
    
    Returns:
        Set[str]: Yüklenmiş handler modül isimleri
    """
    return _LOADED_HANDLERS.copy()

"""
Handler Loader
--------------
Telegram bot handler dosyalarını otomatik yüklemek için yardımcı modül.
Silinen dosyaları otomatik olarak cache'ten temizler.
Tamamen async uyumlu + PEP8 + type hints + singleton + logging destekler.
await clear_handler_cache() veya await get_loaded_handlers() şeklinde çağrılır

"""

import os
import sys
import importlib
import logging
from types import ModuleType
from typing import Any, Callable, Optional, Set, Coroutine, Union

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
        path (str, optional): Handler modüllerinin bulunduğu klasör. Varsayılan: "handlers".

    Raises:
        ImportError: Bir modül yüklenemezse hata loglanır.
        AttributeError: Modülde register fonksiyonu yoksa hata loglanır.
    """
    global _LOADED_HANDLERS

    if not os.path.isdir(path):
        LOG.error("❌ Handler path not found: %s", path)
        return

    # Mevcut handler dosyalarını bul
    current_files: Set[str] = {
        f"{file[:-3]}"
        for file in os.listdir(path)
        if file.endswith(".py") and file != "__init__.py"
    }

    # Cache'i güncelle (silinen dosyaları kaldır)
    _LOADED_HANDLERS = _LOADED_HANDLERS.intersection(current_files)

    # Handler path'ini sys.path'e ekle
    abs_path: str = os.path.abspath(path)
    if abs_path not in sys.path:
        sys.path.insert(0, abs_path)

    for module_name in current_files:
        if module_name in _LOADED_HANDLERS:
            LOG.debug("⚠️ Handler already loaded, skipping: %s", module_name)
            continue

        try:
            # Modülü import et
            module: ModuleType = importlib.import_module(module_name)

            register_func: Optional[
                Union[Callable[[Any], Any], Callable[[Any], Coroutine[Any, Any, Any]]]
            ] = getattr(module, "register", None)

            if register_func is None:
                LOG.warning("⚠️ No register() found in handler: %s", module_name)
                continue

            if callable(register_func):
                result = register_func(application)
                if hasattr(result, "__await__"):  # async ise await et
                    await result
                LOG.info("🟢 Handler loaded: %s", module_name)
                _LOADED_HANDLERS.add(module_name)
            else:
                LOG.warning(
                    "⚠️ Invalid register function type in handler: %s", module_name
                )

        except ImportError as exc:
            LOG.error("❌ Import failed for handler %s: %s", module_name, exc)
        except AttributeError as exc:
            LOG.error("❌ Attribute error in handler %s: %s", module_name, exc)
        except Exception as exc:
            LOG.exception("🚨 Failed to load handler %s: %s", module_name, exc)


async def clear_handler_cache() -> None:
    """
    Handler cache'ini temizler.
    Bu sayede tüm handler'lar yeniden yüklenebilir hale gelir.
    """
    global _LOADED_HANDLERS
    _LOADED_HANDLERS.clear()
    LOG.info("♻️ Handler cache cleared")


async def get_loaded_handlers() -> Set[str]:
    """
    Yüklenmiş handler'ların isimlerini döndürür.

    Returns:
        Set[str]: Yüklenmiş handler modül isimleri.
    """
    return _LOADED_HANDLERS.copy()

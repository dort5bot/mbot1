import os
import importlib
import logging
import sys
from types import ModuleType
from typing import Any, Callable, Optional, Set

LOG: logging.Logger = logging.getLogger("handler_loader")
_LOADED_HANDLERS: Set[str] = set()

async def load_handlers(application: Any, path: str = "handlers") -> None:
    global _LOADED_HANDLERS

    if not os.path.isdir(path):
        LOG.error(f"Handler path not found: {path}")
        return

    # Handler path'ini Python path'ine ekle
    if path not in sys.path:
        sys.path.insert(0, path)

    current_files = {
        f"{file[:-3]}" for file in os.listdir(path) 
        if file.endswith(".py") and file != "__init__.py"
    }
    
    _LOADED_HANDLERS = _LOADED_HANDLERS.intersection(current_files)
    
    for module_name in current_files:
        if module_name in _LOADED_HANDLERS:
            continue

        try:
            # Modülü import et
            module = importlib.import_module(module_name)
            
            register_func = getattr(module, "register", None)
            if register_func and callable(register_func):
                result = register_func(application)
                if hasattr(result, "__await__"):
                    await result
                LOG.info(f"Handler loaded: {module_name}")
                _LOADED_HANDLERS.add(module_name)
                
        except Exception as exc:
            LOG.exception(f"Failed to load handler {module_name}: {exc}")

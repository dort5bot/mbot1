"""
handlers package - Telegram Bot Handlers
----------------------------------------
Aiogram 3.x handler modules organized by functionality.
"""

import logging
from pathlib import Path

# Package-level logger
logger = logging.getLogger(__name__)

# Package version
__version__ = "1.0.0"

# Export common utilities
__all__ = [
    # Will be populated dynamically
]

def discover_handlers() -> list:
    """Discover all handler modules in this package."""
    try:
        handler_dir = Path(__file__).parent
        handlers = []
        
        for py_file in handler_dir.rglob("*.py"):
            if py_file.name.startswith("_") or py_file.name == "__init__.py":
                continue
            
            # Convert to module path
            relative = py_file.relative_to(handler_dir.parent)
            module_path = str(relative.with_suffix("")).replace("/", ".")
            handlers.append(module_path)
        
        return handlers
        
    except Exception as e:
        logger.error(f"Failed to discover handlers: {e}")
        return []

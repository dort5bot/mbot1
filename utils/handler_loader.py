"""
handler_loader.py - Dynamic Handler Loader for Aiogram 3.x (FİNAL)
----------------------------------------------------------
Dynamically loads and registers Telegram bot handlers from modules.
- Async compatible
- Type hints + PEP8 compliant
- Singleton pattern
- Recursive directory scanning
- Automatic module discovery
- Error handling + logging
- Enhanced file filtering
- Non-blocking imports with asyncio.to_thread
Aiogram 3.x Architecture
"""

import asyncio
import importlib
import inspect
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Type, Callable, Awaitable
from types import ModuleType

from aiogram import Dispatcher, Router
from aiogram.types import Update

logger = logging.getLogger(__name__)

# Singleton instance
class HandlerLoader:
    """Singleton class for dynamic handler loading."""
    
    _instance: Optional["HandlerLoader"] = None
    _loaded_handlers: Set[str] = set()
    _handler_cache: Dict[str, ModuleType] = {}
    
    def __new__(cls) -> "HandlerLoader":
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize handler loader."""
        if self._initialized:
            return
            
        self.base_path = Path(__file__).parent.parent / "handlers"
        self._loaded_handlers = set()
        self._handler_cache = {}
        self._initialized = True
        self._loading_stats = {
            "total_loaded": 0,
            "total_failed": 0,
            "last_loading_time": 0,
            "average_loading_time": 0
        }
        logger.info("✅ HandlerLoader singleton initialized")
    
    async def discover_handler_modules(self) -> List[str]:
        """
        Discover all handler modules recursively.
        
        Returns:
            List of module paths (e.g., ['handlers.p_handler', 'handlers.subdir.module'])
        """
        discovered_modules: List[str] = []
        
        try:
            # Walk through handlers directory recursively
            for item in self.base_path.rglob("*.py"):
                # Skip hidden files, __init__.py, and __pycache__ directories
                if (item.name.startswith("_") or 
                    item.name == "__init__.py" or
                    "__pycache__" in str(item) or
                    item.name == "handler_loader.py"):
                    continue
                
                # Convert file path to module path
                relative_path = item.relative_to(self.base_path.parent)
                module_path = str(relative_path.with_suffix("")).replace("/", ".")
                
                if module_path not in self._loaded_handlers:
                    discovered_modules.append(module_path)
            
            logger.info(f"🔍 Discovered {len(discovered_modules)} handler modules")
            return discovered_modules
            
        except Exception as e:
            logger.error(f"❌ Failed to discover handler modules: {e}")
            return []
    
    async def load_handler_module(self, module_path: str) -> Optional[ModuleType]:
        """
        Load a single handler module (async version).
        
        Args:
            module_path: Full module path (e.g., 'handlers.p_handler')
            
        Returns:
            Loaded module or None if failed
        """
        try:
            if module_path in self._handler_cache:
                logger.debug(f"📦 Using cached module: {module_path}")
                return self._handler_cache[module_path]
            
            logger.info(f"📥 Loading handler module: {module_path}")
            
            # Async import using thread pool (non-blocking)
            module = await asyncio.to_thread(importlib.import_module, module_path)
            
            # Validate module structure
            if not await self._is_valid_handler_module(module):
                logger.warning(f"⚠️ Module {module_path} is not a valid handler module")
                return None
            
            self._handler_cache[module_path] = module
            self._loaded_handlers.add(module_path)
            
            logger.info(f"✅ Successfully loaded: {module_path}")
            return module
            
        except ImportError as e:
            logger.error(f"❌ Import failed for {module_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error loading {module_path}: {e}")
            return None
    
    async def _is_valid_handler_module(self, module: ModuleType) -> bool:
        """
        Check if module contains valid handler components.
        
        Args:
            module: Imported module to validate
            
        Returns:
            True if module contains valid handlers
        """
        try:
            # Check for router instance
            if hasattr(module, 'router') and isinstance(module.router, Router):
                return True
            
            # Check for register_handlers function
            if (hasattr(module, 'register_handlers') and 
                callable(module.register_handlers)):
                return True
            
            # Check for register function (common pattern)
            if (hasattr(module, 'register') and 
                callable(module.register)):
                return True
            
            # Check for any function with router registration
            members = inspect.getmembers(module, inspect.isfunction)
            for name, func in members:
                if name.startswith('register_') or 'router' in name.lower():
                    return True
            
            # Check for router instances
            for name, obj in inspect.getmembers(module):
                if isinstance(obj, Router):
                    return True
            
            # Check for message handlers directly
            if hasattr(module, 'message') and callable(module.message):
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"⚠️ Module validation failed: {e}")
            return False
    
    async def register_handlers_from_module(self, module: ModuleType, dispatcher: Dispatcher) -> bool:
        """
        Register handlers from a loaded module.
        
        Args:
            module: Loaded handler module
            dispatcher: Aiogram dispatcher instance
            
        Returns:
            True if registration successful
        """
        try:
            registration_count = 0
            
            # Method 1: Module has a router instance
            if hasattr(module, 'router') and isinstance(module.router, Router):
                dispatcher.include_router(module.router)
                registration_count += 1
                logger.info(f"🔗 Included router from {module.__name__}")
            
            # Method 2: Module has register_handlers function
            if (hasattr(module, 'register_handlers') and 
                callable(module.register_handlers)):
                
                # Check function signature
                sig = inspect.signature(module.register_handlers)
                if 'dispatcher' in sig.parameters:
                    module.register_handlers(dispatcher)
                elif 'router' in sig.parameters:
                    # Create a temporary router
                    temp_router = Router()
                    module.register_handlers(temp_router)
                    dispatcher.include_router(temp_router)
                    registration_count += 1
                else:
                    # Try without parameters
                    result = module.register_handlers()
                    if asyncio.iscoroutine(result):
                        await result
                    registration_count += 1
                
                logger.info(f"🔗 Registered handlers via function from {module.__name__}")
            
            # Method 3: Module has register function (common pattern)
            if (hasattr(module, 'register') and 
                callable(module.register) and 
                registration_count == 0):
                
                sig = inspect.signature(module.register)
                if 'router' in sig.parameters:
                    # Create a temporary router
                    temp_router = Router()
                    module.register(temp_router)
                    dispatcher.include_router(temp_router)
                    registration_count += 1
                    logger.info(f"🔗 Registered via register() function from {module.__name__}")
            
            # Method 4: Manual registration by inspecting functions
            if registration_count == 0:
                registration_count += await self._manual_handler_registration(module, dispatcher)
            
            if registration_count > 0:
                logger.info(f"✅ Registered {registration_count} handler groups from {module.__name__}")
                return True
            else:
                logger.warning(f"⚠️ No handlers found in {module.__name__}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Handler registration failed for {module.__name__}: {e}")
            return False
    
    async def _manual_handler_registration(self, module: ModuleType, dispatcher: Dispatcher) -> int:
        """
        Manually discover and register handlers from module.
        
        Args:
            module: Module to inspect
            dispatcher: Dispatcher instance
            
        Returns:
            Number of handlers registered
        """
        registration_count = 0
        
        try:
            # Look for router instances
            for name, obj in inspect.getmembers(module):
                if isinstance(obj, Router) and name != 'router':
                    dispatcher.include_router(obj)
                    registration_count += 1
                    logger.debug(f"🔗 Included router: {name}")
            
            # Look for registration functions
            for name, func in inspect.getmembers(module, inspect.isfunction):
                if (name.startswith('register_') or name.startswith('setup_')) and callable(func):
                    try:
                        # Check function signature
                        sig = inspect.signature(func)
                        if 'dispatcher' in sig.parameters:
                            func(dispatcher)
                            registration_count += 1
                        elif 'router' in sig.parameters:
                            # Create a new router if function expects one
                            router = Router()
                            func(router)
                            dispatcher.include_router(router)
                            registration_count += 1
                        else:
                            # Try without parameters
                            result = func()
                            if asyncio.iscoroutine(result):
                                await result
                            registration_count += 1
                        
                        logger.debug(f"🔗 Called registration function: {name}")
                    except Exception as e:
                        logger.warning(f"⚠️ Registration function {name} failed: {e}")
            
            return registration_count
            
        except Exception as e:
            logger.error(f"❌ Manual registration failed: {e}")
            return 0
    
    async def load_all_handlers(self, dispatcher: Dispatcher) -> Dict[str, Any]:
        """
        Load and register all discovered handlers.
        
        Args:
            dispatcher: Aiogram dispatcher instance
            
        Returns:
            Dictionary with loading results
        """
        start_time = time.time()
        
        try:
            # Discover all handler modules
            module_paths = await self.discover_handler_modules()
            total_modules = len(module_paths)
            loaded_count = 0
            registered_count = 0
            failed_modules = []
            
            logger.info(f"🔄 Loading {total_modules} handler modules...")
            
            # Load and register each module
            for module_path in module_paths:
                module = await self.load_handler_module(module_path)
                if module:
                    loaded_count += 1
                    if await self.register_handlers_from_module(module, dispatcher):
                        registered_count += 1
                    else:
                        failed_modules.append(module_path)
                else:
                    failed_modules.append(module_path)
            
            # Calculate statistics
            loading_time = time.time() - start_time
            success_rate = (registered_count / total_modules * 100) if total_modules > 0 else 0
            
            # Update loading stats
            self._loading_stats = {
                "total_loaded": loaded_count,
                "total_failed": len(failed_modules),
                "last_loading_time": loading_time,
                "average_loading_time": (
                    (self._loading_stats["average_loading_time"] * 0.7) + 
                    (loading_time * 0.3)
                )
            }
            
            results = {
                "total_modules": total_modules,
                "loaded": loaded_count,
                "registered": registered_count,
                "failed": len(failed_modules),
                "failed_modules": failed_modules,
                "loading_time": f"{loading_time:.2f}s",
                "success_rate": f"{success_rate:.1f}%"
            }
            
            # Log summary
            logger.info(f"📊 Handler loading completed in {loading_time:.2f} seconds")
            logger.info(f"✅ Results: {loaded_count} loaded, {registered_count} registered, {len(failed_modules)} failed")
            logger.info(f"📈 Success rate: {results['success_rate']}")
            
            if failed_modules:
                logger.warning(f"⚠️ Failed modules: {', '.join(failed_modules)}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Critical error during handler loading: {e}")
            return {
                "total_modules": 0,
                "loaded": 0,
                "registered": 0,
                "failed": 0,
                "failed_modules": [],
                "loading_time": "0s",
                "success_rate": "0%",
                "error": str(e)
            }
    
    async def clear_cache(self) -> None:
        """Clear handler cache and loaded modules."""
        self._loaded_handlers.clear()
        self._handler_cache.clear()
        logger.info("🧹 Handler cache cleared")
    
    def get_loaded_modules(self) -> List[str]:
        """Get list of all loaded handler modules."""
        return list(self._loaded_handlers)
    
    def get_cached_modules(self) -> List[str]:
        """Get list of all cached modules."""
        return list(self._handler_cache.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get loader statistics."""
        return {
            "loaded_modules": self.get_loaded_modules(),
            "cached_modules": self.get_cached_modules(),
            "total_loaded": len(self._loaded_handlers),
            "total_cached": len(self._handler_cache),
            "loading_stats": self._loading_stats
        }
    
    async def reload_module(self, module_path: str) -> Optional[ModuleType]:
        """
        Reload a specific module.
        
        Args:
            module_path: Module to reload
            
        Returns:
            Reloaded module or None
        """
        try:
            # Remove from cache
            if module_path in self._handler_cache:
                del self._handler_cache[module_path]
            if module_path in self._loaded_handlers:
                self._loaded_handlers.remove(module_path)
            
            # Reload
            return await self.load_handler_module(module_path)
            
        except Exception as e:
            logger.error(f"❌ Failed to reload module {module_path}: {e}")
            return None

# ---------------------------------------------------------------------
# Global Functions for Backward Compatibility
# ---------------------------------------------------------------------
async def load_handlers(dispatcher: Dispatcher) -> Dict[str, Any]:
    """
    Load all handlers into dispatcher (global function).
    
    Args:
        dispatcher: Aiogram dispatcher instance
        
    Returns:
        Loading results dictionary
    """
    loader = HandlerLoader()
    return await loader.load_all_handlers(dispatcher)

async def clear_handler_cache() -> None:
    """Clear the handler cache (global function)."""
    loader = HandlerLoader()
    await loader.clear_cache()

def get_loaded_handler_count() -> int:
    """Get count of loaded handlers (global function)."""
    loader = HandlerLoader()
    return len(loader.get_loaded_modules())

async def get_handler_stats() -> Dict[str, Any]:
    """Get statistics about loaded handlers."""
    loader = HandlerLoader()
    return loader.get_stats()

async def reload_handler_module(module_path: str) -> Optional[ModuleType]:
    """
    Reload a specific handler module.
    
    Args:
        module_path: Module path to reload
        
    Returns:
        Reloaded module or None
    """
    loader = HandlerLoader()
    return await loader.reload_module(module_path)

# ---------------------------------------------------------------------
# Async Context Manager for Batch Operations
# ---------------------------------------------------------------------
class HandlerLoadingContext:
    """Async context manager for batch handler operations."""
    
    def __init__(self, dispatcher: Dispatcher):
        self.dispatcher = dispatcher
        self.loader = HandlerLoader()
    
    async def __aenter__(self) -> "HandlerLoadingContext":
        """Enter context - clear cache before loading."""
        await self.loader.clear_cache()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context - perform cleanup if needed."""
        if exc_type is not None:
            logger.error(f"❌ Handler loading context failed: {exc_val}")
    
    async def load_with_retry(self, max_retries: int = 3) -> Dict[str, Any]:
        """Load handlers with retry mechanism."""
        for attempt in range(max_retries):
            try:
                results = await self.loader.load_all_handlers(self.dispatcher)
                if results["failed"] == 0:
                    return results
                
                logger.warning(f"🔄 Retry {attempt + 1}/{max_retries} after failures")
                await asyncio.sleep(1 * (attempt + 1))
                
            except Exception as e:
                logger.error(f"❌ Attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
        
        return await self.loader.load_all_handlers(self.dispatcher)

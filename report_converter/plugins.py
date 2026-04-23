"""Plugin system — extensible hooks for custom visual mapping and DAX post-processing.

Allows users to register custom converters without modifying core code.
Supports:
  - Visual type overrides
  - DAX post-processors
  - Expression pre-processors
  - Custom BIRT function handlers
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Callable, Protocol

logger = logging.getLogger(__name__)


class VisualPlugin(Protocol):
    """Protocol for visual mapping plugins."""

    def map_visual(self, element: dict[str, Any]) -> dict[str, Any] | None:
        """Return a PBI visual config or None to skip."""
        ...


class DaxPlugin(Protocol):
    """Protocol for DAX post-processing plugins."""

    def process(self, dax: str, context: dict[str, Any]) -> str:
        """Transform a DAX expression. Return the modified expression."""
        ...


class ExpressionPlugin(Protocol):
    """Protocol for BIRT expression pre-processing plugins."""

    def preprocess(self, expression: str, source: str) -> str:
        """Transform a BIRT expression before conversion."""
        ...


class PluginRegistry:
    """Central registry for migration plugins."""

    def __init__(self):
        self._visual_plugins: list[VisualPlugin] = []
        self._dax_plugins: list[DaxPlugin] = []
        self._expression_plugins: list[ExpressionPlugin] = []
        self._birt_function_handlers: dict[str, Callable[[str], str]] = {}
        self._visual_type_overrides: dict[str, str] = {}
        self._loaded_modules: list[str] = []

    def register_visual_plugin(self, plugin: VisualPlugin) -> None:
        """Register a visual mapping plugin."""
        self._visual_plugins.append(plugin)
        logger.debug("Registered visual plugin: %s", type(plugin).__name__)

    def register_dax_plugin(self, plugin: DaxPlugin) -> None:
        """Register a DAX post-processing plugin."""
        self._dax_plugins.append(plugin)
        logger.debug("Registered DAX plugin: %s", type(plugin).__name__)

    def register_expression_plugin(self, plugin: ExpressionPlugin) -> None:
        """Register an expression pre-processing plugin."""
        self._expression_plugins.append(plugin)
        logger.debug("Registered expression plugin: %s", type(plugin).__name__)

    def register_birt_function(self, function_name: str, handler: Callable[[str], str]) -> None:
        """Register a custom BIRT function → DAX handler.

        Args:
            function_name: e.g. "MyCustom.calculate"
            handler: Takes the full match string, returns DAX.
        """
        self._birt_function_handlers[function_name] = handler

    def register_visual_type_override(self, birt_type: str, pbi_type: str) -> None:
        """Override the default visual type mapping for a BIRT element type."""
        self._visual_type_overrides[birt_type] = pbi_type

    def load_plugin_module(self, module_path: str) -> None:
        """Load a plugin module by dotted path (e.g. 'my_plugins.custom_visuals').

        The module must define a ``register(registry)`` function.
        """
        try:
            mod = importlib.import_module(module_path)
            if hasattr(mod, "register"):
                mod.register(self)
                self._loaded_modules.append(module_path)
                logger.info("Loaded plugin module: %s", module_path)
            else:
                logger.warning("Plugin module %s has no register() function", module_path)
        except ImportError as e:
            logger.error("Failed to import plugin module %s: %s", module_path, e)

    # ── Plugin application ──

    def apply_visual_plugins(self, element: dict[str, Any]) -> dict[str, Any] | None:
        """Apply visual plugins in order. First non-None result wins."""
        for plugin in self._visual_plugins:
            result = plugin.map_visual(element)
            if result is not None:
                return result
        return None

    def apply_dax_plugins(self, dax: str, context: dict[str, Any] | None = None) -> str:
        """Apply all DAX plugins in order."""
        for plugin in self._dax_plugins:
            dax = plugin.process(dax, context or {})
        return dax

    def apply_expression_plugins(self, expression: str, source: str = "") -> str:
        """Apply expression pre-processing plugins in order."""
        for plugin in self._expression_plugins:
            expression = plugin.preprocess(expression, source)
        return expression

    def get_birt_function_handler(self, function_name: str) -> Callable[[str], str] | None:
        """Get a registered handler for a BIRT function."""
        return self._birt_function_handlers.get(function_name)

    def get_visual_type_override(self, birt_type: str) -> str | None:
        """Get a visual type override if registered."""
        return self._visual_type_overrides.get(birt_type)

    def summary(self) -> dict[str, Any]:
        """Return registry summary."""
        return {
            "visual_plugins": len(self._visual_plugins),
            "dax_plugins": len(self._dax_plugins),
            "expression_plugins": len(self._expression_plugins),
            "birt_function_handlers": len(self._birt_function_handlers),
            "visual_type_overrides": len(self._visual_type_overrides),
            "loaded_modules": list(self._loaded_modules),
        }


# Singleton registry
_global_registry: PluginRegistry | None = None


def get_registry() -> PluginRegistry:
    """Get or create the global plugin registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = PluginRegistry()
    return _global_registry


def reset_registry() -> None:
    """Reset the global plugin registry (for testing)."""
    global _global_registry
    _global_registry = None

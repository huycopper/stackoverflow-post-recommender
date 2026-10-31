"""Self-registering normalizers: adding a module in this package needs no dispatcher change."""

from __future__ import annotations

import importlib
import pkgutil

from .base import FieldNormalizer

_NORMALIZERS: dict[tuple[str, str], FieldNormalizer] = {}
_DISCOVERED = False
_NOT_PLUGINS = {"base", "registry"}


def register(normalizer_class: type[FieldNormalizer]) -> type[FieldNormalizer]:
    normalizer = normalizer_class()
    if not isinstance(normalizer, FieldNormalizer):
        raise TypeError(f"{normalizer_class.__name__} must extend FieldNormalizer")
    if normalizer.key in _NORMALIZERS:
        raise ValueError(f"duplicate normalizer registration: {normalizer.key}")
    _NORMALIZERS[normalizer.key] = normalizer
    return normalizer_class


def discover_normalizers() -> None:
    global _DISCOVERED
    if _DISCOVERED:
        return
    package = importlib.import_module(__package__)
    for module in pkgutil.iter_modules(package.__path__):
        if module.name not in _NOT_PLUGINS:
            importlib.import_module(f"{__package__}.{module.name}")
    _DISCOVERED = True


def get_normalizer(target_type: str, profile: str) -> FieldNormalizer:
    discover_normalizers()
    try:
        return _NORMALIZERS[(target_type, profile)]
    except KeyError as err:
        raise ValueError(f"no normalizer registered for {(target_type, profile)}") from err

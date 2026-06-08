import pkgutil
import importlib
import pytest

from tests.isolation_modules import PATCHED_MODULES


def test_no_unpatched_projects_base_dir():
    """Every backend module defining PROJECTS_BASE_DIR must be in PATCHED_MODULES."""
    # Collect all modules in PATCHED_MODULES
    patched_names = {mod.__name__ for mod in PATCHED_MODULES}
    
    # Introspect routers and services packages
    import routers
    import services
    
    unpatched = []
    
    for package in (routers, services):
        for _, module_name, _ in pkgutil.iter_modules(package.__path__):
            full_name = f"{package.__name__}.{module_name}"
            try:
                mod = importlib.import_module(full_name)
            except Exception:
                continue
            if hasattr(mod, "PROJECTS_BASE_DIR"):
                if full_name not in patched_names:
                    unpatched.append(full_name)
    
    assert not unpatched, (
        f"Modules defining PROJECTS_BASE_DIR but not in PATCHED_MODULES: {unpatched}. "
        f"Add them to tests/isolation_modules.py."
    )

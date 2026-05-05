from fastapi import APIRouter
from importlib import import_module
from pathlib import Path

BLACKLIST = {"__init__"}

api_router = APIRouter(prefix="/api")

_api_dir = Path(__file__).parent
for _file in sorted(_api_dir.glob("*.py")):
    _name = _file.stem
    if _name in BLACKLIST:
        continue

    _mod = import_module(f"app.api.{_name}")

    if hasattr(_mod, "router"):
        api_router.include_router(_mod.router)

    if hasattr(_mod, "router_kpi"):
        api_router.include_router(_mod.router_kpi)

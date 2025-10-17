import json
from pathlib import Path
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

MODULES_DIR = Path("modules")
EXCLUDED = {"module_o.json"}


class ModuleInfo(BaseModel):
    id: str
    name: str
    displayText: str
    path: str


@router.get("")
def list_modules() -> List[ModuleInfo]:
    items: List[ModuleInfo] = []
    if not MODULES_DIR.exists():
        return items
    for f in sorted(MODULES_DIR.glob("module_*.json")):
        if f.name in EXCLUDED:
            continue
        try:
            with f.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            module_id = data.get("module", {}).get("id", "")
            module_name = data.get("module", {}).get("name", "")
            if module_id and module_name:
                items.append(ModuleInfo(
                    id=module_id,
                    name=module_name,
                    displayText=f"{module_id} - {module_name}",
                    path=str(f)
                ))
        except Exception:
            letter = f.stem.split("_")[-1].upper()
            items.append(ModuleInfo(
                id=letter,
                name=letter,
                displayText=letter,
                path=str(f)
            ))
    return items



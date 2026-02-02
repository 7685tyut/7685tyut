import json
from pathlib import Path
from typing import Any


def load_storage(path: str) -> dict[str, Any]:
    storage_path = Path(path)
    if not storage_path.exists():
        return {"accounts": [], "groups": {}, "mention_user_id": None}
    with storage_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_storage(path: str, data: dict[str, Any]) -> None:
    storage_path = Path(path)
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    with storage_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def add_account(storage: dict[str, Any], label: str, phone: str, session: str) -> None:
    storage["accounts"].append(
        {
            "label": label,
            "phone": phone,
            "session": session,
        }
    )


def set_groups(storage: dict[str, Any], account_label: str, groups: list[dict[str, Any]]) -> None:
    storage.setdefault("groups", {})[account_label] = groups


def set_mention_user(storage: dict[str, Any], user_id: int | None) -> None:
    storage["mention_user_id"] = user_id

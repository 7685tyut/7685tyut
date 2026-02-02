from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass(frozen=True)
class Config:
    bot_token: str
    api_id: int
    api_hash: str
    admin_ids: list[int]
    storage_path: str
    media_dir: str



def load_config(path: str | None = None) -> Config:
    config_path = Path(path or "config.yaml")
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    return Config(
        bot_token=raw["bot_token"],
        api_id=int(raw["api_id"]),
        api_hash=raw["api_hash"],
        admin_ids=[int(value) for value in raw.get("admin_ids", [])],
        storage_path=raw.get("storage_path", "data/storage.json"),
        media_dir=raw.get("media_dir", "data/media"),
    )

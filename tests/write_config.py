import json, os
from pathlib import Path

cfg = {
    "wiki_root": "./test_wiki", "max_depth": 7,
    "snapshot": {"enabled": True, "cleanup_interval_minutes": 10, "retention_days": 7, "schedule_enabled": True},
    "default_tags": [],
    "transport": {"mode": "local"},
    "remote": {"host": "127.0.0.1", "port": 8000, "path": "/mcp"},
    "logging": {"level": "INFO", "file_enabled": False, "file_path": "./logs/openmem.log", "max_file_size_mb": 10, "backup_count": 5, "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"}
}
path = Path.home() / ".config" / "openmem" / "openmem.json"
path.parent.mkdir(parents=True, exist_ok=True)
with open(path, 'w', encoding='utf-8') as f:
    json.dump(cfg, f, indent=4, ensure_ascii=False)
print(f"written to {path}")
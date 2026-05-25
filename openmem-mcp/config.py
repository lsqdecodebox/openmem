import json
import os
from pathlib import Path
from typing import Optional, Dict, Any

class Config:
    def __init__(self, config_path: str = "openmem.json"):
        # Resolve relative to the directory where this script (config.py) is located
        # This ensures the config is found correctly regardless of working directory
        script_dir = Path(__file__).parent.resolve()
        self.config_path = (script_dir / config_path).resolve()
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    @property
    def wiki_root(self) -> Path:
        return Path(self._config.get("wiki_root", "./wiki")).absolute()
    
    @property
    def llm_config(self) -> Dict[str, Any]:
        return self._config.get("llm", {})
    
    @property
    def max_depth(self) -> int:
        return self._config.get("max_depth", 7)
    
    @property
    def default_tags(self) -> list[str]:
        return self._config.get("default_tags", [])
    
    @property
    def logging_level(self) -> str:
        return self._config.get("logging", {}).get("level", "INFO")

    def save(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)
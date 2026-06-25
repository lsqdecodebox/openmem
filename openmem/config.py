import json
import os
from pathlib import Path
from typing import Optional, Dict, Any

class Config:
    def __init__(self, config_path: str = None):
        if config_path:
            self.config_path = Path(config_path).resolve()
        else:
            self.config_path = self._find_config_path()
        self._config = self._load_config()

    @staticmethod
    def _find_config_path() -> Path:
        if env_path := os.environ.get("OPENMEM_CONFIG"):
            return Path(env_path).resolve()
        user_config = Path.home() / ".config" / "openmem" / "openmem.json"
        if user_config.exists():
            return user_config
        raise FileNotFoundError(
            f"配置文件不存在: {user_config}\n"
            f"请将 openmem.json.example 复制到 {user_config} 后编辑。"
        )

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
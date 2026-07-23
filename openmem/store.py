import json
import shutil
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path

import frontmatter

from openmem.utils import (
    validate_path_depth,
    sanitize_path,
    parse_frontmatter,
    compute_level,
    count_content_chars,
    _strip_markdown,
)

logger = logging.getLogger(__name__)

VALID_ASSET_TYPES = {"images", "files", "videos"}


def _error_json(message: str) -> str:
    return json.dumps({"status": "error", "message": message}, ensure_ascii=False)


class WikiStore:
    def __init__(
        self,
        wiki_root: Path,
        max_depth: int = 7,
        snapshot_cfg: dict | None = None,
    ):
        self.wiki_root = wiki_root.resolve()
        self.max_depth = max_depth

        if snapshot_cfg:
            self.snapshot_enabled = snapshot_cfg.get("enabled", True)
            self.cleanup_interval = snapshot_cfg.get("cleanup_interval_minutes", 10)
            self.retention_days = snapshot_cfg.get("retention_days", 7)
            self.schedule_enabled = snapshot_cfg.get("schedule_enabled", True)
        else:
            self.snapshot_enabled = True
            self.cleanup_interval = 10
            self.retention_days = 7
            self.schedule_enabled = True

        self._timer: threading.Timer | None = None

        if self.snapshot_enabled:
            self._start_timer()

    def get_directory(self, path: str = "/") -> str:
        target_dir = self._resolve_path(path)

        if not target_dir.exists():
            return _error_json(f"目录不存在: {path}")

        if not target_dir.is_dir():
            return _error_json(f"路径不是目录: {path}")

        result = self._build_directory_tree(target_dir)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def read_memory(self, path: str) -> str:
        file_path = self._resolve_page_path(path)

        if not file_path.exists():
            return _error_json(f"页面不存在: {path}")

        if not file_path.is_file():
            return _error_json(f"路径不是文件: {path}")

        content = file_path.read_text(encoding="utf-8")
        logger.debug(f"读取页面: {path}")
        return content

    def write_memory(
        self,
        content: str,
        path: str | None = None,
        tags: list[str] | None = None,
        summary: str | None = None,
    ) -> str:
        if path is None or path.strip() == "":
            return json.dumps(
                {
                    "status": "need_path",
                    "message": "请指定写入路径。请参考核心提示词中的分类规则，确定目标路径。",
                },
                ensure_ascii=False,
            )

        path = sanitize_path(path)
        validation = validate_path_depth(path, self.max_depth)
        if not validation.valid:
            logger.warning(f"路径深度超限: {path}")
            return _error_json(
                f"路径深度超过{self.max_depth}层限制"
            )

        file_path = self._resolve_page_path(path)
        final_summary = summary if summary is not None else self._generate_summary(content)

        if file_path.exists():
            self._create_snapshot(file_path)

            existing = parse_frontmatter(file_path)
            existing.metadata["tags"] = tags if tags is not None else existing.metadata.get("tags", [])
            existing.metadata["summary"] = final_summary
            existing.content = content

            with open(file_path, "w", encoding="utf-8") as f:
                frontmatter.dump(existing, f)

            logger.info(f"更新页面: {path}, 模式: overwrite")
        else:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"自动创建目录: {file_path.parent}")

            level = compute_level(path)
            title = self._extract_title(path)

            post = frontmatter.Post(content)
            post.metadata = {
                "title": title,
                "type": "page",
                "level": level,
                "summary": final_summary,
                "tags": tags or [],
            }

            with open(file_path, "w", encoding="utf-8") as f:
                frontmatter.dump(post, f)

            logger.info(f"创建页面: {path}")

        return json.dumps({"status": "ok", "path": path}, ensure_ascii=False)

    def write_asset(
        self,
        source: str,
        path: str,
        filename: str,
        type: str = "files",
        overwrite: bool = False,
    ) -> str:
        if type not in VALID_ASSET_TYPES:
            return _error_json(f"不支持的文件类型: {type}，仅支持 {', '.join(sorted(VALID_ASSET_TYPES))}")

        if not filename or len(filename.strip()) == 0:
            return _error_json("filename 不能为空")

        try:
            src_path = Path(source).expanduser().resolve()
            if not src_path.exists():
                return _error_json(f"文件不存在: {source}")
            if not src_path.is_file():
                return _error_json(f"路径不是文件: {source}")
            raw_bytes = src_path.read_bytes()
        except OSError as e:
            return _error_json(f"文件读取失败: {str(e)}")

        safe_path = sanitize_path(path)
        safe_filename = Path(filename).name

        asset_dir = self.wiki_root / type / safe_path.lstrip("/")
        asset_dir.mkdir(parents=True, exist_ok=True)

        asset_path = asset_dir / safe_filename

        if asset_path.exists() and not overwrite:
            return json.dumps(
                {
                    "status": "file_exists",
                    "message": f"文件已存在: {type}/{safe_path}/{safe_filename}，使用 overwrite=True 覆盖",
                    "path": f"{type}/{safe_path}/{safe_filename}",
                },
                ensure_ascii=False,
            )

        asset_path.write_bytes(raw_bytes)

        relative_path = f"{type}/{safe_path}/{safe_filename}"
        logger.info(f"写入资产: {relative_path}, 大小: {len(raw_bytes)} 字节")

        return json.dumps(
            {
                "status": "ok",
                "path": relative_path,
                "filename": safe_filename,
                "type": type,
                "size": len(raw_bytes),
            },
            ensure_ascii=False,
        )

    def read_asset(self, path: str) -> str:
        if not path or len(path.strip()) == 0:
            return _error_json("path 不能为空")

        safe_path = sanitize_path(path)
        asset_path = self.wiki_root / safe_path.lstrip("/")

        try:
            asset_path = asset_path.resolve()
        except OSError:
            return _error_json(f"无效路径: {path}")

        if not str(asset_path).startswith(str(self.wiki_root)):
            return _error_json(f"路径不在记忆目录下: {path}")

        if not asset_path.exists():
            return _error_json(f"文件不存在: {path}")

        if not asset_path.is_file():
            return _error_json(f"路径不是文件: {path}")

        file_size = asset_path.stat().st_size

        return json.dumps(
            {
                "status": "ok",
                "absolute_path": str(asset_path),
                "relative_path": safe_path,
                "size": file_size,
            },
            ensure_ascii=False,
        )

    def get_core_principles(self) -> str:
        parts = []
        md_files = sorted(self.wiki_root.glob("*.md"), key=lambda p: p.name)

        for md_file in md_files:
            content = md_file.read_text(encoding="utf-8")
            filename = md_file.stem
            parts.append(f"## {filename}\n\n{content}")

        return "\n\n---\n\n".join(parts)

    def _resolve_path(self, path: str) -> Path:
        if path == "/" or path == "":
            return self.wiki_root
        return self.wiki_root / path.lstrip("/")

    def _resolve_page_path(self, path: str) -> Path:
        resolved = self._resolve_path(path)
        if resolved.suffix != ".md":
            resolved = resolved.with_suffix(".md")
        return resolved

    def _build_directory_tree(self, dir_path: Path) -> dict:
        result = {
            "path": self._relative_path(dir_path),
            "name": dir_path.name or "wiki-root",
            "type": "directory",
            "children": [],
        }

        try:
            entries = sorted(dir_path.iterdir(), key=lambda e: e.name)
        except PermissionError:
            return result

        for entry in entries:
            if entry.name.startswith("."):
                continue

            if entry.is_dir():
                child = {
                    "name": entry.name,
                    "type": "directory",
                    "level": compute_level(self._relative_path(entry)),
                    "children": self._build_directory_tree(entry)["children"],
                }
                result["children"].append(child)

            elif entry.is_file() and entry.suffix == ".md":
                try:
                    fm = parse_frontmatter(entry)
                    child = {
                        "name": entry.name,
                        "type": fm.metadata.get("type", "page"),
                        "level": fm.metadata.get("level", 1),
                        "title": fm.metadata.get("title", entry.stem),
                        "summary": fm.metadata.get("summary", ""),
                    }
                except Exception:
                    child = {
                        "name": entry.name,
                        "type": "page",
                        "level": 1,
                        "title": entry.stem,
                        "summary": "",
                    }
                result["children"].append(child)

        return result

    def _create_snapshot(self, file_path: Path):
        if not self.snapshot_enabled:
            return

        try:
            rel_path = file_path.relative_to(self.wiki_root)
        except ValueError:
            return

        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

        snapshot_dir = self.wiki_root / ".snapshots" / rel_path.with_suffix("")
        snapshot_path = snapshot_dir / f"{timestamp}.md"

        snapshot_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, snapshot_path)

        logger.debug(f"创建快照: {snapshot_path}")

    def _start_timer(self):
        def tick():
            if self.schedule_enabled:
                self._scheduled_snapshot()
            self._cleanup_snapshots()
            self._timer = threading.Timer(
                self.cleanup_interval * 60, tick
            )
            self._timer.daemon = True
            self._timer.start()

        self._timer = threading.Timer(
            self.cleanup_interval * 60, tick
        )
        self._timer.daemon = True
        self._timer.start()
        logger.info(f"快照定时器已启动，间隔: {self.cleanup_interval}分钟")

    def _scheduled_snapshot(self):
        snapshot_count = 0
        for md_file in self.wiki_root.rglob("*.md"):
            try:
                rel = md_file.relative_to(self.wiki_root)
            except ValueError:
                continue

            if str(rel).startswith(".snapshots") or rel.name.startswith("."):
                continue

            latest = self._get_latest_snapshot_time(md_file)
            file_mtime = datetime.fromtimestamp(md_file.stat().st_mtime)

            if latest is None or file_mtime > latest:
                self._create_snapshot(md_file)
                snapshot_count += 1
                logger.info(f"定时快照: {rel}")

        if snapshot_count > 0:
            logger.info(f"定时快照完成，共创建{snapshot_count}个快照")

    def _get_latest_snapshot_time(self, file_path: Path) -> datetime | None:
        try:
            rel_path = file_path.relative_to(self.wiki_root)
        except ValueError:
            return None

        snapshot_dir = self.wiki_root / ".snapshots" / rel_path.with_suffix("")
        if not snapshot_dir.exists():
            return None

        latest_mtime = None
        for snap_file in snapshot_dir.glob("*.md"):
            try:
                mtime = datetime.fromtimestamp(snap_file.stat().st_mtime)
                if latest_mtime is None or mtime > latest_mtime:
                    latest_mtime = mtime
            except OSError:
                continue

        return latest_mtime

    def _cleanup_snapshots(self):
        snapshots_dir = self.wiki_root / ".snapshots"
        if not snapshots_dir.exists():
            return

        cutoff = datetime.now() - timedelta(days=self.retention_days)
        deleted_count = 0
        freed_bytes = 0

        for snapshot_file in snapshots_dir.rglob("*.md"):
            try:
                file_mtime = datetime.fromtimestamp(
                    snapshot_file.stat().st_mtime
                )
                if file_mtime < cutoff:
                    freed_bytes += snapshot_file.stat().st_size
                    snapshot_file.unlink()
                    deleted_count += 1
            except OSError:
                continue

        for dir_path in sorted(snapshots_dir.rglob("*"), reverse=True):
            if dir_path.is_dir():
                try:
                    if not list(dir_path.iterdir()):
                        dir_path.rmdir()
                except OSError:
                    continue

        if deleted_count > 0:
            logger.info(f"快照清理: 删除{deleted_count}个快照，释放{freed_bytes}字节")

    def _relative_path(self, full_path: Path) -> str:
        try:
            rel = full_path.relative_to(self.wiki_root)
        except ValueError:
            return str(full_path)
        return "/" + str(rel).replace("\\", "/")

    def _extract_title(self, path: str) -> str:
        parts = path.strip("/").split("/")
        last = parts[-1] if parts else "未命名"
        return Path(last).stem

    def _generate_summary(self, content: str) -> str:
        try:
            plain = _strip_markdown(content).strip()
        except Exception:
            plain = content.strip()

        if len(plain) > 100:
            return plain[:100] + "..."
        return plain

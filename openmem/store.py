import json
import shutil
import logging
import subprocess
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
    is_directory_summary,
    build_compressed_filenames,
)

logger = logging.getLogger(__name__)

VALID_ASSET_TYPES = {"images", "files", "videos"}


def _is_asset_path(path: str) -> str | None:
    """若 path 首段属于资产类型，返回该类型名；否则返回 None。"""
    if not path:
        return None
    first = path.strip("/").split("/", 1)[0]
    return first if first in VALID_ASSET_TYPES else None


def _error_json(message: str) -> str:
    return json.dumps({"status": "error", "message": message}, ensure_ascii=False)


class WikiStore:
    def __init__(
        self,
        wiki_root: Path,
        max_depth: int = 7,
        snapshot_cfg: dict | None = None,
        max_chars: int = 500000,
    ):
        self.wiki_root = wiki_root.resolve()
        self.max_depth = max_depth
        self.max_chars = max_chars

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
        result = self._compress_tree(result)
        return json.dumps(result, ensure_ascii=False, indent=2)

    def read_memory(self, path: str) -> str:
        asset_type = _is_asset_path(path)
        if asset_type:
            return _error_json(
                f"路径位于资产目录 '{asset_type}/' 下，禁止通过 read_memory 读取，请使用 read_asset 接口"
            )

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

        asset_type = _is_asset_path(path)
        if asset_type:
            return _error_json(
                f"路径位于资产目录 '{asset_type}/' 下，禁止通过 write_memory 写入，请使用 write_asset 接口"
            )

        path = sanitize_path(path)
        validation = validate_path_depth(path, self.max_depth)
        if not validation.valid:
            logger.warning(f"路径深度超限: {path}")
            return _error_json(
                f"路径深度超过{self.max_depth}层限制"
            )

        is_summary = path.rstrip("/").endswith("/summary")
        file_path = self._resolve_page_path(path)
        final_summary = summary if summary is not None else self._generate_summary(content)

        if is_summary:
            content = ""
            final_summary = summary if summary is not None else ""
            level = compute_level(path)

            if file_path.exists():
                self._save_to_history(file_path)

            file_path.parent.mkdir(parents=True, exist_ok=True)
            post = frontmatter.Post("")
            post.metadata = {
                "title": "summary",
                "type": "directory_summary",
                "level": level,
                "summary": final_summary,
                "tags": tags or [],
            }

            with open(file_path, "w", encoding="utf-8") as f:
                frontmatter.dump(post, f)

            self._update_baseline(file_path)
            logger.info(f"写入目录摘要: {path}")
            return json.dumps({"status": "ok", "path": path}, ensure_ascii=False)

        if file_path.exists():
            self._save_to_history(file_path)

            existing = parse_frontmatter(file_path)
            existing.metadata["tags"] = tags if tags is not None else existing.metadata.get("tags", [])
            existing.metadata["summary"] = final_summary
            existing.content = content

            with open(file_path, "w", encoding="utf-8") as f:
                frontmatter.dump(existing, f)

            self._update_baseline(file_path)
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

            self._update_baseline(file_path)
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

    def search_memory(
        self,
        pattern: str,
        path: str = "/",
        is_regex: bool = False,
        case_sensitive: bool = False,
        whole_word: bool = False,
        context: int = 0,
        max_results: int = 50,
    ) -> str:
        """在记忆中检索包含指定模式的页面，对齐 ``grep -r -n`` 行为。

        通过 ``subprocess`` 调用系统 grep（macOS/Linux），固定排除
        ``.snapshots/`` 与 ``images/files/videos`` 资产目录。返回 ``output``
        字段为 grep 原始 stdout 风格文本，命中行用 ``:`` 分隔，上下文行用
        ``-`` 分隔，跨文件命中块用 ``--`` 分隔。

        Args:
            pattern: 搜索模式（固定字符串或扩展正则）
            path: 搜索范围，wiki 内子树路径，默认 ``/`` 全 wiki
            is_regex: True=按扩展正则匹配（-E），False=固定字符串（-F）
            case_sensitive: True=大小写敏感，False=忽略大小写（-i）
            whole_word: True=词边界匹配（-w）
            context: 上下文行数（-C），默认 0 不带上下文
            max_results: 返回输出行数上限，超出则截断并标记 truncated

        Returns:
            JSON 字符串，含 status/pattern/scope/total_matches/returned_matches/
            truncated/output 字段；错误时返回 ``{"status":"error","message":...}``
        """
        if not pattern:
            return _error_json("pattern 不能为空")

        safe_path = sanitize_path(path)
        search_root = self.wiki_root / safe_path.lstrip("/")
        try:
            search_root = search_root.resolve()
        except OSError:
            return _error_json(f"无效路径: {path}")

        if not str(search_root).startswith(str(self.wiki_root)):
            return _error_json(f"路径不在记忆目录下: {path}")

        if not search_root.exists():
            return _error_json(f"路径不存在: {path}")

        if not search_root.is_dir():
            return _error_json(f"路径不是目录: {path}")

        cmd = [
            "grep", "-r", "-n", "--color=never",
            "--include=*.md",
            "--exclude-dir=.snapshots",
            "--exclude-dir=images",
            "--exclude-dir=files",
            "--exclude-dir=videos",
        ]
        if not case_sensitive:
            cmd.append("-i")
        if whole_word:
            cmd.append("-w")
        cmd.append("-E" if is_regex else "-F")
        if context > 0:
            cmd += ["-C", str(context)]
        cmd.append("--")
        cmd.append(pattern)
        cmd.append("." if not safe_path.lstrip("/") else "./" + safe_path.lstrip("/"))

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.wiki_root),
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return _error_json("搜索超时")
        except OSError as e:
            return _error_json(f"执行 grep 失败: {e}")

        if proc.returncode == 2:
            err_msg = proc.stderr.strip() or "grep 执行错误"
            return _error_json(f"grep 错误: {err_msg}")

        lines = proc.stdout.splitlines() if proc.stdout else []
        normalized_lines = [
            "/" + line[2:] if line.startswith("./") else line for line in lines
        ]

        total_matches = len(normalized_lines)
        truncated = total_matches > max_results
        returned_lines = normalized_lines[:max_results]

        logger.debug(
            f"search_memory: pattern={pattern!r}, scope={path}, "
            f"total={total_matches}, returned={len(returned_lines)}"
        )

        return json.dumps(
            {
                "status": "ok",
                "pattern": pattern,
                "scope": path,
                "total_matches": total_matches,
                "returned_matches": len(returned_lines),
                "truncated": truncated,
                "output": "\n".join(returned_lines),
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

        is_root = dir_path.resolve() == self.wiki_root

        for entry in entries:
            if entry.name.startswith("."):
                continue

            if is_root and entry.is_dir() and entry.name in VALID_ASSET_TYPES:
                continue

            if entry.is_dir():
                sub = self._build_directory_tree(entry)
                child = {
                    "name": entry.name,
                    "type": "directory",
                    "level": compute_level(self._relative_path(entry)),
                    "children": sub["children"],
                }
                if "summary" in sub:
                    child["summary"] = sub["summary"]
                if "tags" in sub:
                    child["tags"] = sub["tags"]
                result["children"].append(child)

            elif entry.is_file() and entry.suffix == ".md":
                if is_directory_summary(entry):
                    try:
                        fm = parse_frontmatter(entry)
                        result["summary"] = fm.metadata.get("summary", "")
                        result["tags"] = fm.metadata.get("tags", [])
                    except Exception:
                        result["summary"] = ""
                        result["tags"] = []
                    continue

                try:
                    fm = parse_frontmatter(entry)
                    child = {
                        "name": entry.name,
                        "type": fm.metadata.get("type", "page"),
                        "level": fm.metadata.get("level", 1),
                        "summary": fm.metadata.get("summary", ""),
                    }
                except Exception:
                    child = {
                        "name": entry.name,
                        "type": "page",
                        "level": 1,
                        "summary": "",
                    }
                result["children"].append(child)

        return result

    def _compress_tree(self, tree: dict) -> dict:
        chars = len(json.dumps(tree, ensure_ascii=False))
        if chars <= self.max_chars:
            return tree

        while chars > self.max_chars:
            target = self._find_deepest_compressible(tree)
            if target is None:
                break

            file_nodes = [c for c in target["children"] if c["type"] != "directory" and not c["name"].startswith("_compressed")]
            if len(file_nodes) < 2:
                target.setdefault("_compressed_disabled", True)
                continue

            filenames = [f["name"] for f in file_nodes]
            count, names_str = build_compressed_filenames(filenames)
            target["_compressed_filecount"] = count
            target["_compressed_filenames"] = names_str
            target["children"] = [c for c in target["children"] if c["type"] == "directory"]

            chars = len(json.dumps(tree, ensure_ascii=False))

        return tree

    def _find_deepest_compressible(self, node: dict) -> dict | None:
        """后序 DFS，返回最深的、含 ≥2 个非 directory 文件节点且未压缩过的目录节点"""
        best = None
        best_depth = -1

        def dfs(n: dict, depth: int):
            nonlocal best, best_depth
            if n.get("type") != "directory":
                return
            if n.get("_compressed_disabled"):
                return

            file_count = sum(
                1 for c in n.get("children", [])
                if c.get("type") != "directory" and not c.get("name", "").startswith("_compressed")
            )

            if file_count >= 2 and depth > best_depth:
                best = n
                best_depth = depth

            for c in reversed(n.get("children", [])):
                if c.get("type") == "directory":
                    dfs(c, depth + 1)

        dfs(node, 0)
        return best

    def _save_to_history(self, file_path: Path, logical_rel_path: Path | None = None):
        """把 file_path 当前内容存入 history，时间戳=存档动作发生的当下。

        用于 write_memory 覆盖旧版本前、定时任务基线更新前保存被取代的版本。

        logical_rel_path 用于组织 history 子目录结构：默认按 file_path 自身的相对路径，
        当 file_path 是基线文件（位于 .snapshots/.current/ 下）时，调用方应传入
        对应源文件的 rel_path，使历史快照按源路径归档。
        """
        if logical_rel_path is None:
            try:
                logical_rel_path = file_path.relative_to(self.wiki_root)
            except ValueError:
                return

        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        dst = self.wiki_root / ".snapshots" / "history" / logical_rel_path.with_suffix("") / f"{timestamp}.md"

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, dst)

        logger.debug(f"存入历史: {dst}")

    def _update_baseline(self, file_path: Path):
        """把 file_path 当前内容覆盖写入 .current 基线（镜像源路径）。

        基线始终反映源文件的当前状态，豁免清理。
        """
        try:
            rel_path = file_path.relative_to(self.wiki_root)
        except ValueError:
            return

        dst = self.wiki_root / ".snapshots" / ".current" / rel_path

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, dst)

        logger.debug(f"更新基线: {dst}")

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
        scanned = 0
        baseline_updated = 0
        history_added = 0

        for md_file in self.wiki_root.rglob("*.md"):
            try:
                rel = md_file.relative_to(self.wiki_root)
            except ValueError:
                continue

            if str(rel).startswith(".snapshots") or rel.name.startswith("."):
                continue

            scanned += 1

            baseline = self.wiki_root / ".snapshots" / ".current" / rel
            src_mtime = datetime.fromtimestamp(md_file.stat().st_mtime)

            if not baseline.exists():
                self._update_baseline(md_file)
                baseline_updated += 1
                logger.debug(f"建立基线: {rel}")
            else:
                base_mtime = datetime.fromtimestamp(baseline.stat().st_mtime)
                if src_mtime > base_mtime:
                    self._save_to_history(baseline, rel)
                    self._update_baseline(md_file)
                    baseline_updated += 1
                    history_added += 1
                    logger.debug(f"基线更新: {rel}")

        logger.info(
            f"定时快照完成：扫描{scanned}个，更新基线{baseline_updated}个，新增历史{history_added}个"
        )

    def _cleanup_snapshots(self):
        history_dir = self.wiki_root / ".snapshots" / "history"
        if not history_dir.exists():
            return

        cutoff = datetime.now() - timedelta(days=self.retention_days)
        deleted_count = 0
        freed_bytes = 0

        for snapshot_file in history_dir.rglob("*.md"):
            try:
                created = datetime.strptime(
                    snapshot_file.stem, "%Y-%m-%dT%H-%M-%S"
                )
            except ValueError:
                continue

            if created < cutoff:
                freed_bytes += snapshot_file.stat().st_size
                snapshot_file.unlink()
                deleted_count += 1

        for dir_path in sorted(history_dir.rglob("*"), reverse=True):
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

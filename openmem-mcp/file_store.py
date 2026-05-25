import frontmatter
import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class FileStore:
    def __init__(self, wiki_root: Path, max_depth: int = 7):
        self.wiki_root = wiki_root
        self.max_depth = max_depth
        self._ensure_root_directory()
    
    def _ensure_root_directory(self):
        """确保根目录和根目录.md存在"""
        self.wiki_root.mkdir(parents=True, exist_ok=True)
        
        root_index = self.wiki_root / "目录.md"
        if not root_index.exists():
            self._write_page(
                path=root_index,
                front_matter={
                    "title": "我的个人知识库",
                    "path": "/",
                    "type": "directory",
                    "level": 1,
                    "parent": None,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "summary": "这是我的个人Wiki知识库，包含个人生活、工作记录和技术知识。",
                    "tags": ["知识库", "个人Wiki"],
                    "source": "auto"
                },
                content="# 我的个人知识库\n\n## 主要目录\n\n欢迎使用您的个人Wiki知识库！"
            )
    
    def _get_absolute_path(self, path: str) -> Path:
        """将相对路径转换为绝对路径"""
        if path.startswith("/"):
            path = path[1:]
        return self.wiki_root / path
    
    def _write_page(self, path: Path, front_matter: Dict[str, Any], content: str):
        """原子写入Markdown文件"""
        temp_path = path.with_suffix(".tmp")
        
        try:
            post = frontmatter.Post(content, **front_matter)
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(frontmatter.dumps(post))
            
            # 原子重命名
            os.replace(temp_path, path)
            logger.info(f"成功写入文件: {path}")
        except Exception as e:
            if temp_path.exists():
                os.remove(temp_path)
            logger.error(f"写入文件失败: {path}, 错误: {e}")
            raise
    
    def read_page(self, path: str) -> Optional[frontmatter.Post]:
        """读取指定路径的页面"""
        abs_path = self._get_absolute_path(path)
        if not abs_path.exists() or not abs_path.is_file():
            return None
        
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                return frontmatter.load(f)
        except Exception as e:
            logger.error(f"读取文件失败: {abs_path}, 错误: {e}")
            return None
    
    def read_directory(self, path: str = "/") -> Optional[Dict[str, Any]]:
        """读取指定目录的目录.md"""
        if path == "/" or path == "":
            index_path = "目录.md"
        else:
            index_path = os.path.join(path, "目录.md")
        
        return self.read_page(index_path)
    
    def create_directory(self, path: str, title: str, summary: str, parent_path: str) -> bool:
        """创建新目录和对应的目录.md"""
        # 检查深度
        level = path.strip("/").count("/") + 2
        if level > self.max_depth:
            logger.error(f"目录深度超过限制: {level} > {self.max_depth}")
            return False
        
        abs_path = self._get_absolute_path(path)
        if abs_path.exists():
            logger.error(f"目录已存在: {path}")
            return False
        
        try:
            abs_path.mkdir(parents=True, exist_ok=True)
            
            # 创建目录.md
            index_path = abs_path / "目录.md"
            self._write_page(
                path=index_path,
                front_matter={
                    "title": title,
                    "path": path,
                    "type": "directory",
                    "level": level,
                    "parent": parent_path,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "summary": summary,
                    "tags": [],
                    "source": "auto"
                },
                content=f"# {title}\n\n## 子目录\n\n"
            )
            
            # 更新父目录
            self._update_directory_index(parent_path, path, title, "directory")
            
            return True
        except Exception as e:
            logger.error(f"创建目录失败: {path}, 错误: {e}")
            return False
    
    def create_page(self, path: str, title: str, content: str, summary: str, 
                   parent_path: str, tags: List[str] = None, source: str = "auto") -> bool:
        """创建新页面"""
        # 检查深度
        level = path.strip("/").count("/") + 2
        if level > self.max_depth:
            logger.error(f"页面深度超过限制: {level} > {self.max_depth}")
            return False
        
        abs_path = self._get_absolute_path(path)
        if abs_path.exists():
            logger.error(f"页面已存在: {path}")
            return False
        
        try:
            # 确保父目录存在
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 确保父目录有目录.md（递归创建缺失的父目录索引）
            self._ensure_parent_directory_index(parent_path)
            
            self._write_page(
                path=abs_path,
                front_matter={
                    "title": title,
                    "path": path,
                    "type": "page",
                    "level": level,
                    "parent": parent_path,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "summary": summary,
                    "tags": tags or [],
                    "source": source
                },
                content=content
            )
            
            # 更新父目录索引
            self._update_directory_index(parent_path, path, title, "page")
            
            return True
        except Exception as e:
            logger.error(f"创建页面失败: {path}, 错误: {e}")
            return False
    
    def update_page(self, path: str, content: str, summary: str = None) -> bool:
        """更新现有页面"""
        post = self.read_page(path)
        if not post:
            logger.error(f"页面不存在: {path}")
            return False
        
        try:
            post.content = content
            post.metadata["updated_at"] = datetime.now().isoformat()
            if summary:
                post.metadata["summary"] = summary
            
            abs_path = self._get_absolute_path(path)
            self._write_page(abs_path, post.metadata, post.content)
            
            return True
        except Exception as e:
            logger.error(f"更新页面失败: {path}, 错误: {e}")
            return False
    
    def _ensure_parent_directory_index(self, directory_path: str):
        """递归确保父目录的目录.md存在（从根向下逐级检查）"""
        if directory_path == "/" or not directory_path:
            return
        
        # 检查父目录是否有目录.md
        dir_post = self.read_directory(directory_path)
        if dir_post:
            return  # 已存在
        
        # 递归确保更上级目录存在
        parent_of_parent = str(Path(directory_path).parent).replace("\\", "/")
        if parent_of_parent == ".":
            parent_of_parent = "/"
        self._ensure_parent_directory_index(parent_of_parent)
        
        # 创建缺失的目录.md
        dir_name = Path(directory_path).name
        md_rel_path = directory_path.lstrip("/") + "/目录.md"
        self._write_page(
            path=self._get_absolute_path(md_rel_path),
            front_matter={
                "title": dir_name,
                "path": directory_path,
                "type": "directory",
                "level": directory_path.strip("/").count("/") + 2,
                "parent": parent_of_parent,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "summary": f"{dir_name} 目录",
                "tags": [],
                "source": "auto"
            },
            content=f"# {dir_name}\n\n## 子目录\n\n"
        )
        
        # 更新上级目录索引
        self._update_directory_index(parent_of_parent, directory_path, dir_name, "directory")
    
    def _update_directory_index(self, directory_path: str, item_path: str, 
                               item_title: str, item_type: str) -> bool:
        """更新目录的索引文件"""
        dir_post = self.read_directory(directory_path)
        if not dir_post:
            logger.error(f"目录不存在: {directory_path}")
            return False
        
        try:
            # 生成相对链接
            if directory_path == "/":
                rel_path = item_path.lstrip("/")
            else:
                rel_path = os.path.relpath(item_path, directory_path).replace("\\", "/")
            
            if item_type == "directory":
                link = f"[[{rel_path}/目录.md|{item_title}]]"
            else:
                link = f"[[{rel_path}|{item_title}]]"
            
            # 检查是否已存在
            if link not in dir_post.content:
                # 添加到子目录列表
                if "## 子目录" in dir_post.content:
                    parts = dir_post.content.split("## 子目录", 1)
                    dir_post.content = parts[0] + "## 子目录\n- " + link + "\n" + parts[1]
                else:
                    dir_post.content += "\n## 子目录\n- " + link + "\n"
                
                dir_post.metadata["updated_at"] = datetime.now().isoformat()
                
                abs_path = self._get_absolute_path(
                    "目录.md" if directory_path == "/" else directory_path.lstrip("/") + "/目录.md"
                )
                self._write_page(abs_path, dir_post.metadata, dir_post.content)
            
            return True
        except Exception as e:
            logger.error(f"更新目录索引失败: {directory_path}, 错误: {e}")
            return False
    
    def list_directory_items(self, directory_path: str) -> List[Dict[str, str]]:
        """列出目录下的所有子条目"""
        dir_post = self.read_directory(directory_path)
        if not dir_post:
            return []
        
        items = []
        
        # 从目录.md中提取子条目
        abs_dir_path = self._get_absolute_path(directory_path.lstrip("/"))
        
        # 遍历目录下的所有文件和子目录
        for item in abs_dir_path.iterdir():
            if item.name == "目录.md" or item.name.startswith("."):
                continue
            
            if item.is_dir():
                # 子目录
                sub_index = item / "目录.md"
                if sub_index.exists():
                    sub_post = self.read_page(directory_path.rstrip("/") + "/" + item.name + "/目录.md")
                    if sub_post:
                        items.append({
                            "title": sub_post.metadata.get("title", item.name),
                            "path": directory_path.rstrip("/") + "/" + item.name,
                            "summary": sub_post.metadata.get("summary", ""),
                            "type": "directory"
                        })
            elif item.is_file() and item.suffix == ".md":
                # Markdown页面
                page_post = self.read_page(directory_path.rstrip("/") + "/" + item.name)
                if page_post:
                    items.append({
                        "title": page_post.metadata.get("title", item.stem),
                        "path": directory_path.rstrip("/") + "/" + item.name,
                        "summary": page_post.metadata.get("summary", ""),
                        "type": "page"
                    })
        
        return items
    
    def export_wiki(self, output_path: str = "wiki_export.zip") -> str:
        """导出整个Wiki为ZIP文件"""
        output_path = Path(output_path)
        shutil.make_archive(output_path.with_suffix(""), "zip", self.wiki_root)
        return str(output_path.absolute())
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging
import os
from file_store import FileStore
from llm_client import LLMClient

logger = logging.getLogger(__name__)

class WriteEngine:
    def __init__(self, file_store: FileStore, llm_client: LLMClient):
        self.file_store = file_store
        self.llm_client = llm_client
    
    def add_memory(self, content: str, suggested_path: str = None, 
                  tags: List[str] = None, source: str = "Claude对话") -> str:
        """添加新记忆，自动分类到最合适的位置"""
        logger.info(f"添加新记忆: {content[:50]}...")
        
        # 如果有建议路径，直接使用
        if suggested_path:
            return self._add_to_path(content, suggested_path, tags, source)
        
        # 否则从根目录开始渐进式匹配
        return self._find_best_location_and_add(content, "/", tags, source)
    
    def _find_best_location_and_add(self, content: str, current_path: str, 
                                   tags: List[str] = None, source: str = "auto") -> str:
        """从当前目录开始，找到最合适的位置添加内容"""
        # 获取当前目录的子条目
        items = self.file_store.list_directory_items(current_path)
        
        if not items:
            # 空目录，直接创建新页面
            return self._create_new_page(content, current_path, tags, source)
        
        # 让LLM选择最合适的子条目
        selected_paths = self.llm_client.select_best_match(content, items, top_k=1)
        
        if not selected_paths:
            # 没有合适的子条目，创建新页面
            return self._create_new_page(content, current_path, tags, source)
        
        selected_path = selected_paths[0]
        selected_item = next((i for i in items if i["path"] == selected_path), None)
        
        if not selected_item:
            return self._create_new_page(content, current_path, tags, source)
        
        if selected_item["type"] == "directory":
            # 递归进入子目录
            return self._find_best_location_and_add(content, selected_path, tags, source)
        else:
            # 更新现有页面
            return self._update_existing_page(content, selected_path)
    
    def _add_to_path(self, content: str, path: str, 
                    tags: List[str] = None, source: str = "auto") -> str:
        """将内容添加到指定路径"""
        if path.endswith(".md"):
            # 指定的是页面
            if self.file_store.read_page(path):
                return self._update_existing_page(content, path)
            else:
                # 创建新页面
                title = self._generate_title(content)
                summary = self.llm_client.generate_summary(content)
                parent_path = str(Path(path).parent).replace("\\", "/")
                
                if self.file_store.create_page(path, title, content, summary, parent_path, tags, source):
                    return path
                else:
                    raise Exception(f"创建页面失败: {path}")
        else:
            # 指定的是目录
            return self._create_new_page(content, path, tags, source)
    
    def _create_new_page(self, content: str, parent_path: str, 
                        tags: List[str] = None, source: str = "auto") -> str:
        """在指定目录下创建新页面"""
        title = self._generate_title(content)
        # 生成安全的文件名
        filename = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).rstrip() + ".md"
        path = os.path.join(parent_path, filename).replace("\\", "/")
        summary = self.llm_client.generate_summary(content)
        
        if self.file_store.create_page(path, title, content, summary, parent_path, tags, source):
            return path
        else:
            raise Exception(f"创建页面失败: {path}")
    
    def _update_existing_page(self, content: str, page_path: str, mode: str = "merge") -> str:
        """更新现有页面"""
        post = self.file_store.read_page(page_path)
        if not post:
            raise Exception(f"页面不存在: {page_path}")
        
        if mode == "append":
            # 直接追加
            new_content = post.content + "\n\n" + content
        elif mode == "overwrite":
            # 直接覆盖
            new_content = content
        else:
            # 智能合并
            messages = [
                {"role": "system", "content": "请将新内容智能合并到现有文档中，保持文档结构清晰，避免重复。只返回合并后的文档内容。"},
                {"role": "user", "content": f"现有文档:\n{post.content}\n\n新内容:\n{content}"}
            ]
            new_content = self.llm_client.chat_completion(messages, use_large_model=True)
        
        # 重新生成摘要
        summary = self.llm_client.generate_summary(new_content)
        
        if self.file_store.update_page(page_path, new_content, summary):
            return page_path
        else:
            raise Exception(f"更新页面失败: {page_path}")
    
    def _generate_title(self, content: str) -> str:
        """为内容生成合适的标题"""
        messages = [
            {"role": "system", "content": "请为以下内容生成一个简洁明了的标题，不超过20个字。"},
            {"role": "user", "content": content}
        ]
        return self.llm_client.chat_completion(messages, use_large_model=False)
    
    def update_memory(self, path: str, content: str, mode: str = "merge") -> bool:
        """更新指定路径的记忆"""
        try:
            self._update_existing_page(content, path, mode)
            return True
        except Exception as e:
            logger.error(f"更新记忆失败: {e}")
            return False
    
    def create_directory(self, path: str, title: str, summary: str) -> bool:
        """创建新目录"""
        parent_path = str(Path(path).parent).replace("\\", "/")
        if parent_path == ".":
            parent_path = "/"
        
        return self.file_store.create_directory(path, title, summary, parent_path)
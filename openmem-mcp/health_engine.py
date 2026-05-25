from pathlib import Path
from typing import List, Dict, Any
import logging
from file_store import FileStore
from llm_client import LLMClient

logger = logging.getLogger(__name__)

class HealthEngine:
    def __init__(self, file_store: FileStore, llm_client: LLMClient):
        self.file_store = file_store
        self.llm_client = llm_client
    
    def run_check(self) -> Dict[str, Any]:
        """运行完整的健康检查"""
        logger.info("开始运行健康检查...")
        
        report = {
            "total_files": 0,
            "total_directories": 0,
            "errors": [],
            "warnings": [],
            "suggestions": []
        }
        
        # 递归遍历所有文件和目录
        self._check_directory("/", report)
        
        logger.info(f"健康检查完成: {len(report['errors'])}个错误, {len(report['warnings'])}个警告")
        return report
    
    def _check_directory(self, path: str, report: Dict[str, Any]):
        """检查单个目录"""
        # 检查目录.md是否存在
        dir_post = self.file_store.read_directory(path)
        if not dir_post:
            report["errors"].append(f"目录缺少目录.md: {path}")
            return
        
        report["total_directories"] += 1
        
        # 检查Front Matter完整性
        required_fields = ["title", "path", "type", "level", "parent", "created_at", "updated_at", "summary", "tags", "source"]
        for field in required_fields:
            if field not in dir_post.metadata:
                report["errors"].append(f"目录缺少必填字段: {path} -> {field}")
        
        # 检查层级
        if dir_post.metadata.get("level", 0) > self.file_store.max_depth:
            report["errors"].append(f"目录深度超过限制: {path} ({dir_post.metadata.get('level')})")
        
        # 检查子条目
        items = self.file_store.list_directory_items(path)
        
        for item in items:
            if item["type"] == "directory":
                self._check_directory(item["path"], report)
            else:
                self._check_page(item["path"], report)
    
    def _check_page(self, path: str, report: Dict[str, Any]):
        """检查单个页面"""
        post = self.file_store.read_page(path)
        if not post:
            report["errors"].append(f"无法读取页面: {path}")
            return
        
        report["total_files"] += 1
        
        # 检查Front Matter完整性
        required_fields = ["title", "path", "type", "level", "parent", "created_at", "updated_at", "summary", "tags", "source"]
        for field in required_fields:
            if field not in post.metadata:
                report["errors"].append(f"页面缺少必填字段: {path} -> {field}")
        
        # 检查层级
        if post.metadata.get("level", 0) > self.file_store.max_depth:
            report["errors"].append(f"页面深度超过限制: {path} ({post.metadata.get('level')})")
        
        # 检查内容长度
        if len(post.content.strip()) < 20:
            report["warnings"].append(f"页面内容过短: {path}")
        
        # 检查摘要是否准确
        if len(post.metadata.get("summary", "")) > 150:
            report["warnings"].append(f"页面摘要过长: {path}")
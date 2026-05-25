from typing import Optional, List, Dict, Any
import logging
from file_store import FileStore
from llm_client import LLMClient

logger = logging.getLogger(__name__)

class ReadEngine:
    def __init__(self, file_store: FileStore, llm_client: LLMClient):
        self.file_store = file_store
        self.llm_client = llm_client
    
    def search(self, query: str, max_depth: int = 7, max_results: int = 3) -> str:
        """从根目录开始渐进式搜索"""
        logger.info(f"搜索查询: {query}")

        results = []
        try:
            self._search_recursive(query, "/", results, max_depth, 1)
        except Exception as e:
            logger.error(f"搜索过程中出错: {e}")

        if not results:
            return "没有找到相关的记忆。"

        # 让LLM重排结果并生成回答
        return self._generate_answer(query, results[:max_results])
    
    def _search_recursive(self, query: str, current_path: str, 
                         results: List[Dict[str, Any]], max_depth: int, current_level: int):
        """递归搜索目录"""
        if current_level > max_depth:
            return
        
        # 获取当前目录的子条目
        items = self.file_store.list_directory_items(current_path)
        
        if not items:
            return
        
        # 让LLM选择最相关的条目
        selected_paths = self.llm_client.select_best_match(query, items, top_k=2)
        
        for path in selected_paths:
            item = next((i for i in items if i["path"] == path), None)
            if not item:
                continue
            
            if item["type"] == "directory":
                # 递归搜索子目录
                self._search_recursive(query, path, results, max_depth, current_level + 1)
            else:
                # 读取页面内容并添加到结果
                post = self.file_store.read_page(path)
                if post:
                    results.append({
                        "path": path,
                        "title": post.metadata.get("title", ""),
                        "content": post.content,
                        "summary": post.metadata.get("summary", "")
                    })
    
    def _generate_answer(self, query: str, results: List[Dict[str, Any]]) -> str:
        """根据搜索结果生成回答"""
        if not results:
            return "没有找到相关的记忆。"
        
        context = "\n\n".join([
            f"## {r['title']}\n{r['content']}\n来源: {r['path']}"
            for r in results
        ])
        
        messages = [
            {"role": "system", "content": "请根据以下上下文回答用户的问题。如果上下文没有相关信息，请明确说明。引用信息时请注明来源。"},
            {"role": "user", "content": f"用户问题: {query}\n\n上下文:\n{context}"}
        ]
        
        return self.llm_client.chat_completion(messages, use_large_model=True)
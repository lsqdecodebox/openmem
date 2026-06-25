from openai import OpenAI
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, config: Dict[str, Any]):
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.api_key = config.get("api_key", "")
        self.small_model = config.get("small_model", "gpt-4o-mini")
        self.large_model = config.get("large_model", "gpt-4o")
        self.timeout = config.get("timeout", 30)
        
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout
        )
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        use_large_model: bool = False,
        temperature: float = 0.1,
        max_tokens: int = 1000
    ) -> str:
        model = self.large_model if use_large_model else self.small_model
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            raise
    
    def generate_summary(self, content: str, max_length: int = 100) -> str:
        """生成内容摘要"""
        messages = [
            {"role": "system", "content": f"请用不超过{max_length}字总结以下内容，语言简洁明了。"},
            {"role": "user", "content": content}
        ]
        return self.chat_completion(messages, use_large_model=False)
    
    def select_best_match(self, query: str, candidates: List[Dict[str, str]], top_k: int = 2) -> List[str]:
        """从候选列表中选择最相关的条目"""
        if not candidates:
            return []

        candidates_text = "\n".join([f"- {i+1}. {c['title']}: {c['summary']}" for i, c in enumerate(candidates)])
        
        messages = [
            {"role": "system", "content": f"用户查询：{query}\n\n请从以下候选条目中选择最相关的{top_k}个，只返回编号，用逗号分隔。"},
            {"role": "user", "content": candidates_text}
        ]
        
        result = self.chat_completion(messages, use_large_model=False)
        selected_indices = [int(i.strip())-1 for i in result.split(",") if i.strip().isdigit()]
        
        return [candidates[i]["path"] for i in selected_indices if 0 <= i < len(candidates)]
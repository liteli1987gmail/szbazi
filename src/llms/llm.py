"""
LLM 调用层
支持 OpenAI / DeepSeek / 任何兼容 OpenAI 格式的接口
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import openai


class BaseLLM(ABC):
    @abstractmethod
    def chat(self, messages: List[Dict], temperature: float = 0.3) -> str:
        pass


class OpenAILLM(BaseLLM):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: Optional[str] = None):
        self.model = model
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url,   # None = 默认 OpenAI；填入 DeepSeek URL 即可切换
        )

    def chat(self, messages: List[Dict], temperature: float = 0.3) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        return resp.choices[0].message.content.strip()


def create_llm(config) -> BaseLLM:
    """根据 config 创建 LLM 实例"""
    return OpenAILLM(
        api_key=config.OPENAI_API_KEY,
        model=config.OPENAI_MODEL,
        base_url=getattr(config, "OPENAI_BASE_URL", None),
    )

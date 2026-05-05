"""
MiniMax LLM 调用层
使用 Anthropic SDK 兼容 MiniMax API
"""
import time
from typing import List, Dict
from anthropic import Anthropic, RateLimitError, APIError


class MiniMaxLLM:
    def __init__(self, api_key: str, base_url: str = "https://api.minimaxi.com/anthropic", model: str = "MiniMax-M2", max_retries: int = 5):
        self.client = Anthropic(api_key=api_key, base_url=base_url)
        self.model = model
        self.max_retries = max_retries

    def chat(self, messages: List[Dict], temperature: float = 0.3) -> str:
        for attempt in range(self.max_retries):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    temperature=temperature,
                    messages=messages,
                )
                return "".join([block.text for block in response.content if hasattr(block, 'text')])
            except RateLimitError as e:
                if attempt < self.max_retries - 1:
                    wait = (attempt + 1) * 5  # 5, 10, 15, 20, 25 秒
                    time.sleep(wait)
                    continue
                raise
            except APIError as e:
                if attempt < self.max_retries - 1:
                    time.sleep(10)
                    continue
                raise


def create_minimax_llm(api_key: str, base_url: str = "https://api.minimaxi.com/anthropic", model: str = "MiniMax-M2") -> MiniMaxLLM:
    return MiniMaxLLM(api_key=api_key, base_url=base_url, model=model)

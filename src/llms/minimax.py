"""
MiniMax LLM 调用层
使用 Anthropic SDK 兼容 MiniMax API
"""
from typing import List, Dict
from anthropic import Anthropic


class MiniMaxLLM:
    def __init__(self, api_key: str, base_url: str = "https://api.minimaxi.com/anthropic", model: str = "MiniMax-M2"):
        self.client = Anthropic(api_key=api_key, base_url=base_url)
        self.model = model

    def chat(self, messages: List[Dict], temperature: float = 0.3) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=temperature,
            messages=messages,
        )
        return "".join([block.text for block in response.content if hasattr(block, 'text')])


def create_minimax_llm(api_key: str, base_url: str = "https://api.minimaxi.com/anthropic", model: str = "MiniMax-M2") -> MiniMaxLLM:
    return MiniMaxLLM(api_key=api_key, base_url=base_url, model=model)

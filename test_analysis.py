"""
八字分析测试脚本
使用 MiniMax LLM
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from src.llms.minimax import create_minimax_llm
from src.tools.database import BookDatabase
from src.nodes.nodes import BookAnalysisNode

# 配置
API_KEY = os.getenv("ANTHROPIC_API_KEY")
BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
MODEL = "MiniMax-M2"

print(f"使用 MiniMax API: {BASE_URL}")
print(f"Model: {MODEL}")

# 创建 LLM
llm = create_minimax_llm(API_KEY, BASE_URL, MODEL)

# 测试调用
print("\n测试 LLM 调用...")
messages = [
    {"role": "user", "content": "你好，请用一句话介绍自己"}
]
response = llm.chat(messages)
print(f"LLM 响应: {response}")

# 加载数据库
print("\n加载数据库...")
db = BookDatabase("data/bazi_knowledge.db")
books = db.get_all_books()
print(f"数据库中 {len(books)} 本书")

# 找到三命通会
sanming = None
for book in books:
    if "sanming_tonghui" in book["book_id"]:
        sanming = book
        break

if sanming:
    print(f"\n找到书籍: {sanming['book_name']}")
    paragraphs = db.get_paragraphs_by_book(sanming["book_id"])
    print(f"段落数: {len(paragraphs)}")

    # 测试单段落分析
    if paragraphs:
        para = paragraphs[0]
        print(f"\n测试分析第一个段落...")
        print(f"段落内容: {para.content[:80]}...")

        node = BookAnalysisNode(llm)
        from src.state.state import ParagraphConclusion

        # 直接调用 LLM 测试
        test_messages = [
            {"role": "system", "content": "你是一位精通八字命理的古籍研究专家。"},
            {"role": "user", "content": f"八字：甲子乙丑丙寅丁卯\n\n古籍段落（来自《{para.book_name}》）：\n{para.content}\n\n请分析该段落与此八字的关系，给出简短结论："}
        ]
        result = llm.chat(test_messages)
        print(f"\n分析结论: {result}")
else:
    print("未找到三命通会！")

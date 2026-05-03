"""
八字分析脚本
使用 MiniMax LLM + 三命通会数据库
"""
import os
import sys
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

import types
from src.llms.minimax import create_minimax_llm
from src.tools.database import BookDatabase
from src.state.state import Paragraph, ParagraphConclusion
import uuid
import time

# 配置
API_KEY = os.getenv('ANTHROPIC_API_KEY')
BASE_URL = os.getenv('ANTHROPIC_BASE_URL', 'https://api.minimaxi.com/anthropic')
MODEL = "MiniMax-M2"

print(f"=" * 60)
print(f"八字古籍分析系统")
print(f"=" * 60)
print(f"LLM: {MODEL}")
print(f"API: {BASE_URL}")
print(f"=" * 60)

# 创建 LLM
llm = create_minimax_llm(API_KEY, BASE_URL, MODEL)

# 加载数据库
db = BookDatabase("data/bazi_knowledge.db")
books = db.get_all_books()

# 找到三命通会
sanming_book = None
for book in books:
    if "sanming_tonghui" in book["book_id"]:
        sanming_book = book
        break

if not sanming_book:
    print("错误：未找到三命通会！")
    sys.exit(1)

print(f"\n书籍: {sanming_book['book_name']}")
paragraphs = db.get_paragraphs_by_book(sanming_book["book_id"])
print(f"段落数: {len(paragraphs)}")

# 用户输入八字
bazi = input("\n请输入八字（例：甲子 乙丑 丙寅 丁卯）: ").strip()
if not bazi:
    bazi = "甲子 乙丑 丙寅 丁卯"
print(f"分析八字: {bazi}")

# 系统提示词
SYSTEM_PROMPT = """你是一位精通八字命理的古籍研究专家。
你的任务是：给定一个八字和一段古籍原文，分析这个八字与该段落描述的命理规律之间的关系，推导出具体的结论。

要求：
- 结论必须针对这个八字的具体情况
- 不要泛泛而谈，要指出段落中哪个规律与该八字对应
- 如果段落内容与该八字无关，直接返回"无关"
- 用简洁的中文输出结论，100字以内"""

print(f"\n{'=' * 60}")
print(f"开始分析...")
print(f"{'=' * 60}\n")

# 逐段落分析
conclusions = []
total = len(paragraphs)

for idx, para in enumerate(paragraphs):
    print(f"[{idx+1}/{total}] 分析: {para.content[:40]}...")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"八字：{bazi}\n\n古籍段落（来自《{para.book_name}》第{para.sequence}段）：\n{para.content}\n\n请分析该段落规律与此八字的关系，给出结论："}
    ]

    try:
        result = llm.chat(messages)
        if "无关" not in result:
            conclusion = ParagraphConclusion(
                conclusion_id=str(uuid.uuid4()),
                paragraph=para,
                bazi_input=bazi,
                conclusion_text=result,
                created_at=time.time(),
            )
            conclusions.append(conclusion)
            print(f"  => {result[:60]}...")
        else:
            print(f"  => 无关")
    except Exception as e:
        print(f"  => 错误: {e}")

print(f"\n{'=' * 60}")
print(f"分析完成！")
print(f"共分析 {total} 个段落，得到 {len(conclusions)} 条相关结论")
print(f"{'=' * 60}")

# 显示结论
if conclusions:
    print(f"\n【命理结论】\n")
    for i, c in enumerate(conclusions, 1):
        print(f"{i}. 《{c.paragraph.book_name}》")
        print(f"   原文: {c.paragraph.content[:50]}...")
        print(f"   结论: {c.conclusion_text}")
        print()

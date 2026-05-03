"""
Stage 4 独立脚本：基于已有结论+变体，直接综合生成最终结论
（不需要跑 Stage 3 的全量比对，适合快速出结果）

用法：
    python reports/synthesize_variants.py <session_id> [top_n]

示例：
    python reports/synthesize_variants.py 3b983d14-6275-4298-b328-19a2507e6a23 10
"""
import sys, os, types, uuid, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from src.tools.database import BookDatabase
from src.llms.minimax import MiniMaxLLM
from src.state.state import FinalConclusion
import os

DB_PATH = "data/bazi_knowledge.db"
TOP_N = 10


def build_synthesis_prompt(bazi: str, conclusions: list, correct_variants: list, incorrect_variants: list) -> tuple:
    """构建综合分析的 prompt（不依赖比对结果）"""

    # 从正确变体提取全量核心结论
    correct_lines = []
    for v in correct_variants:
        correct_lines.append(f"- 【正】{v['variant_text']}")

    # 从错误变体提取全量矛盾观点
    incorrect_lines = []
    for v in incorrect_variants:
        incorrect_lines.append(f"- 【反】{v['variant_text']}")

    # 结论来源全量摘要
    conclusion_lines = []
    for c in conclusions:
        conclusion_lines.append(f"- 《{c['book_name']}》第{c['sequence']}段：{c['conclusion_text']}")

    system_prompt = """你是一位资深命理综合分析师。
用户输入了一个八字，已经通过古籍分析得到：
- 多本古籍的段落结论（N条）
- 正向变体（对结论的正面表述，2N中的"对"变体）
- 负向变体（对结论的反面/质疑表述，2N中的"错"变体）

你的任务是根据这些材料，给出该八字的最终命理分析报告。

要求：
- 综合正反两面观点，指出主要特征和需要注意之处
- 指出哪些结论得到多处印证（强结论）
- 指出哪些结论存在矛盾或需要进一步验证
- 给出整体命理特征、用神建议
- 使用专业但易读的语言，Markdown 格式输出最终报告"""

    user_prompt = f"""八字：{bazi}

【古籍段落结论（{len(conclusions)}条）】
""" + "\n".join(conclusion_lines) + f"""

【正向变体（{len(correct_variants)}条，对结论的正面支持）】
""" + "\n".join(correct_lines) + f"""

【负向变体（{len(incorrect_variants)}条，对结论的质疑/反面观点）】
""" + "\n".join(incorrect_lines) + """

请综合以上全部材料，输出最终命理分析报告："""

    return system_prompt, user_prompt


def run_synthesis(bazi: str, conclusions: list, correct_variants: list, incorrect_variants: list, top_n: int = 10) -> FinalConclusion:
    """调用 LLM 生成综合结论"""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
    model = os.getenv("ANTHROPIC_MODEL", "MiniMax-M2")

    llm = MiniMaxLLM(api_key=api_key, base_url=base_url, model=model)

    system_prompt, user_prompt = build_synthesis_prompt(bazi, conclusions, correct_variants, incorrect_variants)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    print("  调用 LLM 生成综合结论...")
    synthesis = llm.chat(messages, temperature=0.5)

    return FinalConclusion(
        bazi_input=bazi,
        correct_comparisons=[],
        incorrect_comparisons=[],
        synthesis=synthesis,
    )


def main():
    if len(sys.argv) < 2:
        # 自动找最新的有结论的 session
        db = BookDatabase(DB_PATH)
        sessions = db.get_analysis_sessions()
        active = [s for s in sessions if db.get_session_conclusions(s["session_id"])]
        if not active:
            print("没有找到有结论的分析会话，请先运行完整分析流程")
            return
        session = active[0]
        print(f"自动选择最新会话: {session['session_id']} | 八字: {session['bazi_input']}")
    else:
        session_id = sys.argv[1]
        db = BookDatabase(DB_PATH)
        sessions = db.get_analysis_sessions()
        session = next((s for s in sessions if s["session_id"] == session_id), None)
        if not session:
            print(f"未找到 session: {session_id}")
            return

    session_id = session["session_id"]
    bazi = session["bazi_input"]
    top_n = int(sys.argv[2]) if len(sys.argv) > 2 else TOP_N

    print(f"\n{'='*60}")
    print(f"八字: {bazi}")
    print(f"Session: {session_id}")
    print(f"Top-N: {top_n}")
    print(f"{'='*60}")

    # 加载结论
    conclusions = db.get_session_conclusions(session_id)
    print(f"  结论: {len(conclusions)} 条")

    # 加载变体
    variants = db.get_session_variants(session_id)
    correct_variants = [v for v in variants if v["variant_type"] == "correct"]
    incorrect_variants = [v for v in variants if v["variant_type"] == "incorrect"]
    print(f"  正向变体: {len(correct_variants)} 条")
    print(f"  负向变体: {len(incorrect_variants)} 条")

    if not conclusions or not variants:
        print("结论或变体数据不足，无法综合")
        return

    # 生成综合结论
    result = run_synthesis(bazi, conclusions, correct_variants, incorrect_variants)

    print(f"\n{'='*60}")
    print("【最终综合结论】")
    print(f"{'='*60}")
    print(result.synthesis)

    # 保存到数据库
    db.update_final_conclusion(session_id, result.synthesis)
    print(f"\n[已保存到数据库 session: {session_id}]")

    # 同时保存到文件
    import json
    os.makedirs("reports", exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    json_path = f"reports/synthesis_{bazi.replace(' ', '_')}_{ts}.json"
    md_path = f"reports/synthesis_{bazi.replace(' ', '_')}_{ts}.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "bazi": bazi,
            "session_id": session_id,
            "conclusions_count": len(conclusions),
            "correct_variants_count": len(correct_variants),
            "incorrect_variants_count": len(incorrect_variants),
            "synthesis": result.synthesis,
            "created_at": time.time(),
        }, f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# 八字综合分析报告\n\n")
        f.write(f"**八字:** {bazi}\n\n")
        f.write(f"**Session:** {session_id}\n\n")
        f.write(f"**数据:** {len(conclusions)}条结论 / {len(correct_variants)}正向变体 / {len(incorrect_variants)}负向变体\n\n")
        f.write(f"---\n\n")
        f.write(result.synthesis)

    print(f"[JSON: {json_path}]")
    print(f"[MD:   {md_path}]")


if __name__ == "__main__":
    main()

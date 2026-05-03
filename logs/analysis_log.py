"""
八字分析日志模块
保存每次分析的结果
"""
import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def save_analysis_log(bazi: str, conclusions: list, variant_records: list = None,
                       correct_results: list = None, incorrect_results: list = None,
                       final_conclusion: str = None, config: dict = None):
    """
    保存分析日志

    Args:
        bazi: 八字
        conclusions: 段落结论列表
        variant_records: 变体记录列表
        correct_results: 对组比对结果
        incorrect_results: 错组比对结果
        final_conclusion: 最终结论
        config: 分析配置
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_id = f"{bazi.replace(' ', '')}_{timestamp}"

    # 创建日志条目
    log_entry = {
        "log_id": log_id,
        "timestamp": timestamp,
        "bazi": bazi,
        "config": config or {},
        "statistics": {
            "conclusions_count": len(conclusions) if conclusions else 0,
            "variant_records_count": len(variant_records) if variant_records else 0,
            "correct_results_count": len(correct_results) if correct_results else 0,
            "incorrect_results_count": len(incorrect_results) if incorrect_results else 0,
        },
        "conclusions": [],
        "variant_records": [],
        "correct_results": [],
        "incorrect_results": [],
        "final_conclusion": final_conclusion,
    }

    # 保存结论
    if conclusions:
        for c in conclusions:
            log_entry["conclusions"].append({
                "book_name": c.paragraph.book_name if hasattr(c, 'paragraph') else "",
                "paragraph_content": c.paragraph.content if hasattr(c, 'paragraph') else "",
                "conclusion_text": c.conclusion_text if hasattr(c, 'conclusion_text') else str(c),
            })

    # 保存变体记录
    if variant_records:
        for v in variant_records:
            log_entry["variant_records"].append({
                "variant_type": v.variant_type.value if hasattr(v, 'variant_type') else "",
                "variant_text": v.variant_text if hasattr(v, 'variant_text') else str(v),
            })

    # 保存比对结果
    if correct_results:
        for r in correct_results:
            log_entry["correct_results"].append({
                "variant_text": r.variant_record.variant_text if hasattr(r, 'variant_record') else "",
                "paragraph_content": r.compared_paragraph.content if hasattr(r, 'compared_paragraph') else "",
                "relationship": r.relationship if hasattr(r, 'relationship') else "",
                "relevance_score": r.relevance_score if hasattr(r, 'relevance_score') else 0,
            })

    if incorrect_results:
        for r in incorrect_results:
            log_entry["incorrect_results"].append({
                "variant_text": r.variant_record.variant_text if hasattr(r, 'variant_record') else "",
                "paragraph_content": r.compared_paragraph.content if hasattr(r, 'compared_paragraph') else "",
                "relationship": r.relationship if hasattr(r, 'relationship') else "",
                "relevance_score": r.relevance_score if hasattr(r, 'relevance_score') else 0,
            })

    # 保存 JSON 文件
    json_path = LOG_DIR / f"{log_id}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(log_entry, f, ensure_ascii=False, indent=2)

    # 保存 Markdown 报告
    md_path = LOG_DIR / f"{log_id}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# 八字分析报告\n\n")
        f.write(f"**八字:** {bazi}\n\n")
        f.write(f"**时间:** {timestamp}\n\n")
        f.write(f"**配置:** {json.dumps(config, ensure_ascii=False, indent=2) if config else '默认'}\n\n")
        f.write(f"---\n\n")
        f.write(f"## 统计\n\n")
        f.write(f"- 段落结论: {log_entry['statistics']['conclusions_count']} 条\n")
        f.write(f"- 变体记录: {log_entry['statistics']['variant_records_count']} 条\n")
        f.write(f"- 对组比对: {log_entry['statistics']['correct_results_count']} 条\n")
        f.write(f"- 错组比对: {log_entry['statistics']['incorrect_results_count']} 条\n\n")

        if final_conclusion:
            f.write(f"---\n\n## 最终结论\n\n{final_conclusion}\n\n")

        if conclusions:
            f.write(f"---\n\n## 段落结论\n\n")
            for i, c in enumerate(conclusions, 1):
                f.write(f"### {i}. 《{c.get('book_name', '')}》\n\n")
                f.write(f"**原文:** {c.get('paragraph_content', '')[:200]}...\n\n")
                f.write(f"**结论:** {c.get('conclusion_text', '')}\n\n")

    return log_id, json_path, md_path


def list_analysis_logs():
    """列出所有分析日志"""
    logs = []
    for f in sorted(LOG_DIR.glob("*.json"), reverse=True):
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
            logs.append({
                "log_id": data["log_id"],
                "timestamp": data["timestamp"],
                "bazi": data["bazi"],
                "conclusions_count": data["statistics"]["conclusions_count"],
            })
    return logs

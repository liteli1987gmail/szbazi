"""
将 Checkpoint JSON + PKL 导入数据库
用法: python reports/import_checkpoint.py
"""
import sys, os, json, uuid, time, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.tools.database import BookDatabase
from src.state.state import ParagraphConclusion, Paragraph, VariantRecord, VariantType

DB_PATH = "data/bazi_knowledge.db"

def load_conclusions_from_json(data):
    """从 JSON 数据构建 ParagraphConclusion 对象列表"""
    conclusions = []
    for book_id, concs in data["conclusions_by_book"].items():
        for c in concs:
            para_data = c["paragraph"]
            para = Paragraph(
                paragraph_id=para_data["paragraph_id"],
                book_id=para_data["book_id"],
                book_name=para_data["book_name"],
                content=para_data["content"],
                sequence=para_data["sequence"],
            )
            conclusions.append(ParagraphConclusion(
                conclusion_id=c["conclusion_id"],
                paragraph=para,
                bazi_input=c["bazi_input"],
                conclusion_text=c["conclusion_text"],
                created_at=c["created_at"],
            ))
    return conclusions


def import_pkl(pkl_path: str, bazi: str):
    """从 PKL 文件导入完整的分析状态"""
    with open(pkl_path, "rb") as f:
        state = pickle.load(f)

    db = BookDatabase(DB_PATH)
    db._ensure_analysis_schema()

    print(f"导入八字: {bazi}")
    print(f"Stage: {state.stage}")

    # 创建会话
    session_id = db.save_analysis_session(bazi=bazi, config={"source": "pkl_checkpoint", "stage": state.stage})

    # 导入结论
    all_conclusions = [c for clist in state.conclusions_by_book.values() for c in clist]
    if all_conclusions:
        db.save_conclusions(session_id, all_conclusions)
        print(f"  结论: {len(all_conclusions)} 条")

    # 导入变体
    if state.variant_records:
        db.save_variants(session_id, state.variant_records)
        print(f"  变体: {len(state.variant_records)} 条")

    print(f"  Session ID: {session_id}")
    return session_id


if __name__ == "__main__":
    bazi = "丙申  戊戌  戊辰 辛酉"

    db = BookDatabase(DB_PATH)
    db._ensure_analysis_schema()

    # 找到已有的 session（结论已入库的那个）
    sessions = db.get_analysis_sessions(bazi)
    session_with_conclusions = None
    for s in sessions:
        concs = db.get_session_conclusions(s['session_id'])
        if concs:
            session_with_conclusions = s['session_id']
            break

    if session_with_conclusions:
        print(f"找到已有 session: {session_with_conclusions[:20]}...")
        # 导入变体到已有 session
        with open("reports/stage2_variants.pkl", "rb") as f:
            state = pickle.load(f)
        db.save_variants(session_with_conclusions, state.variant_records)
        print(f"  导入变体: {len(state.variant_records)} 条")
    else:
        # 完整导入
        print("处理: stage2_variants.pkl (最新检查点)")
        import_pkl("reports/stage2_variants.pkl", bazi)

    # 验证
    print("\n=== 验证数据库 ===")
    sessions = db.get_analysis_sessions(bazi)
    for s in sessions:
        print(f"  Session: {s['session_id'][:20]}... | created: {s['created_at']}")
        concs = db.get_session_conclusions(s['session_id'])
        variants = db.get_session_variants(s['session_id'])
        print(f"    结论: {len(concs)} 条 | 变体: {len(variants)} 条")

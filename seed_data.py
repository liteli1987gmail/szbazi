"""
测试数据初始化脚本
向数据库写入示例书籍和段落，方便本地调试
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.tools.database import BookDatabase

SAMPLE_BOOKS = [
    {
        "book_id": "book_a",
        "book_name": "三命通会",
        "paragraphs": [
            "甲日主生于寅月，得月令之气，为建禄格，主人志气高昂，事业有成。",
            "年柱甲子，天干甲木，地支子水生木，此为相生之象，主家世良好。",
            "日支坐印，主得母荫，早年受家庭庇护，中年后自立门户。",
            "时柱逢财，晚年财运亨通，子女有出息，家庭和睦。",
            "天干透出比劫，主竞争激烈，宜从事需要协作之行业。",
        ],
    },
    {
        "book_id": "book_b",
        "book_name": "滴天髓",
        "paragraphs": [
            "木旺得火，方化其顽，无火则木气郁结，主人性格执拗，难以变通。",
            "水木相生，聪明灵秀，若水多木浮，则漂泊无根，居所不定。",
            "甲木参天，脱胎要火，春夏之木，调候为先。",
            "庚金克甲，若有丙火化之，化杀为权，主人有领导才能。",
            "印星旺盛，主聪慧好学，但过旺则懒惰依赖，缺乏进取心。",
        ],
    },
    {
        "book_id": "book_c",
        "book_name": "子平真诠",
        "paragraphs": [
            "用神为喜，忌神为凶，八字分析首重用神之确立。",
            "财官印食，四吉神也，煞伤枭劫，四凶神也，得地则凶化吉。",
            "日主强弱，为八字分析之根本，强则泄秀，弱则扶助。",
            "大运流年与命局之配合，决定人生各阶段之吉凶祸福。",
            "命局有情，大运有力，两者相辅相成，方能成就大业。",
        ],
    },
]


def seed(db_path: str = "data/bazi_knowledge.db"):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db = BookDatabase(db_path)
    count = 0
    for book in SAMPLE_BOOKS:
        db.insert_book(book["book_id"], book["book_name"])
        for seq, content in enumerate(book["paragraphs"], start=1):
            para_id = f"{book['book_id']}_p{seq}"
            db.insert_paragraph(para_id, book["book_id"], seq, content)
            count += 1
    print(f"✅ 已写入 {len(SAMPLE_BOOKS)} 本书，共 {count} 个段落")
    print(f"   数据库：{db_path}")


if __name__ == "__main__":
    seed()

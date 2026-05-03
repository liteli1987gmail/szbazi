"""
数据库工具模块
从数据库读取已分段的书籍内容

数据库表结构（示例）：
  CREATE TABLE books (
      book_id   TEXT PRIMARY KEY,
      book_name TEXT NOT NULL
  );

  CREATE TABLE paragraphs (
      paragraph_id TEXT PRIMARY KEY,
      book_id      TEXT NOT NULL,
      sequence     INTEGER NOT NULL,
      content      TEXT NOT NULL,
      FOREIGN KEY (book_id) REFERENCES books(book_id)
  );
"""
import sqlite3
import time
from typing import List, Optional
from ..state.state import Paragraph


class BookDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        """确保表结构存在（开发期自动建表）"""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS books (
                    book_id   TEXT PRIMARY KEY,
                    book_name TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS paragraphs (
                    paragraph_id TEXT PRIMARY KEY,
                    book_id      TEXT NOT NULL,
                    sequence     INTEGER NOT NULL,
                    content      TEXT NOT NULL,
                    FOREIGN KEY (book_id) REFERENCES books(book_id)
                );
            """)

    # ── 读取接口 ──────────────────────────────────────

    def get_all_books(self) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM books ORDER BY book_id").fetchall()
        return [dict(r) for r in rows]

    def get_paragraphs_by_book(self, book_id: str) -> List[Paragraph]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT p.*, b.book_name FROM paragraphs p "
                "JOIN books b ON p.book_id = b.book_id "
                "WHERE p.book_id = ? ORDER BY p.sequence",
                (book_id,)
            ).fetchall()
        return [
            Paragraph(
                paragraph_id=r["paragraph_id"],
                book_id=r["book_id"],
                book_name=r["book_name"],
                content=r["content"],
                sequence=r["sequence"],
            )
            for r in rows
        ]

    def get_all_paragraphs(self) -> List[Paragraph]:
        """获取所有书的全部段落（用于回溯比对阶段）"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT p.*, b.book_name FROM paragraphs p "
                "JOIN books b ON p.book_id = b.book_id "
                "ORDER BY p.book_id, p.sequence"
            ).fetchall()
        return [
            Paragraph(
                paragraph_id=r["paragraph_id"],
                book_id=r["book_id"],
                book_name=r["book_name"],
                content=r["content"],
                sequence=r["sequence"],
            )
            for r in rows
        ]

    def count_paragraphs(self, book_id: Optional[str] = None) -> int:
        with self._conn() as conn:
            if book_id:
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM paragraphs WHERE book_id=?", (book_id,)
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) AS c FROM paragraphs").fetchone()
        return row["c"]

    # ── 写入接口（初始化数据用）──────────────────────────

    def insert_book(self, book_id: str, book_name: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO books VALUES (?, ?)", (book_id, book_name)
            )

    def insert_paragraph(self, paragraph_id: str, book_id: str, sequence: int, content: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO paragraphs VALUES (?, ?, ?, ?)",
                (paragraph_id, book_id, sequence, content),
            )

    # ── 分析结果存储（按八字查询）───────────────────────

    def _ensure_analysis_schema(self):
        """确保分析结果表结构存在"""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS analysis_sessions (
                    session_id    TEXT PRIMARY KEY,
                    bazi_input    TEXT NOT NULL,
                    created_at    REAL NOT NULL,
                    config        TEXT,
                    final_conclusion TEXT
                );

                CREATE TABLE IF NOT EXISTS conclusions (
                    conclusion_id    TEXT PRIMARY KEY,
                    session_id       TEXT NOT NULL,
                    book_id          TEXT NOT NULL,
                    book_name        TEXT NOT NULL,
                    paragraph_id     TEXT NOT NULL,
                    sequence         INTEGER NOT NULL,
                    paragraph_content TEXT NOT NULL,
                    conclusion_text  TEXT NOT NULL,
                    created_at       REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES analysis_sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS variants (
                    variant_id        TEXT PRIMARY KEY,
                    session_id        TEXT NOT NULL,
                    source_conclusion_id TEXT NOT NULL,
                    variant_type      TEXT NOT NULL,
                    variant_text      TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES analysis_sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS comparison_results (
                    result_id         TEXT PRIMARY KEY,
                    session_id        TEXT NOT NULL,
                    variant_id        TEXT NOT NULL,
                    compared_book_id  TEXT NOT NULL,
                    compared_book_name TEXT NOT NULL,
                    compared_paragraph_id TEXT NOT NULL,
                    compared_sequence INTEGER NOT NULL,
                    compared_content  TEXT NOT NULL,
                    relationship      TEXT NOT NULL,
                    relevance_score   REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES analysis_sessions(session_id)
                );

                CREATE INDEX IF NOT EXISTS idx_conclusions_bazi ON conclusions(session_id);
                CREATE INDEX IF NOT EXISTS idx_variants_bazi ON variants(session_id);
                CREATE INDEX IF NOT EXISTS idx_comparison_bazi ON comparison_results(session_id);
            """)

    def save_analysis_session(self, bazi: str, config: dict = None) -> str:
        """创建分析会话，返回 session_id"""
        import uuid
        import json
        self._ensure_analysis_schema()
        session_id = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO analysis_sessions VALUES (?, ?, ?, ?, ?)",
                (session_id, bazi, time.time(), json.dumps(config or {}), None)
            )
        return session_id

    def update_final_conclusion(self, session_id: str, final_conclusion: str):
        """分析完成后更新最终结论"""
        with self._conn() as conn:
            conn.execute(
                "UPDATE analysis_sessions SET final_conclusion=? WHERE session_id=?",
                (final_conclusion, session_id)
            )

    def save_conclusions(self, session_id: str, conclusions: list):
        """批量保存段落结论"""
        self._ensure_analysis_schema()
        with self._conn() as conn:
            for c in conclusions:
                p = c.paragraph if hasattr(c, 'paragraph') else c.get('paragraph')
                conn.execute(
                    """INSERT INTO conclusions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        c.conclusion_id if hasattr(c, 'conclusion_id') else c.get('conclusion_id', ''),
                        session_id,
                        p.book_id if hasattr(p, 'book_id') else p.get('book_id', ''),
                        p.book_name if hasattr(p, 'book_name') else p.get('book_name', ''),
                        p.paragraph_id if hasattr(p, 'paragraph_id') else p.get('paragraph_id', ''),
                        p.sequence if hasattr(p, 'sequence') else p.get('sequence', 0),
                        p.content if hasattr(p, 'content') else p.get('content', ''),
                        c.conclusion_text if hasattr(c, 'conclusion_text') else str(c.get('conclusion_text', '')),
                        c.created_at if hasattr(c, 'created_at') else time.time(),
                    )
                )

    def save_variants(self, session_id: str, variants: list):
        """批量保存变体记录"""
        with self._conn() as conn:
            for v in variants:
                conn.execute(
                    """INSERT INTO variants VALUES (?, ?, ?, ?, ?)""",
                    (
                        v.variant_id,
                        session_id,
                        v.source_conclusion.conclusion_id,
                        v.variant_type.value,
                        v.variant_text,
                    )
                )

    def save_comparison_results(self, session_id: str, correct_results: list, incorrect_results: list):
        """批量保存比对结果"""
        with self._conn() as conn:
            for r in correct_results + incorrect_results:
                p = r.compared_paragraph
                conn.execute(
                    """INSERT INTO comparison_results VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        r.result_id,
                        session_id,
                        r.variant_record.variant_id,
                        p.book_id,
                        p.book_name,
                        p.paragraph_id,
                        p.sequence,
                        p.content,
                        r.relationship,
                        r.relevance_score,
                    )
                )

    def get_analysis_sessions(self, bazi: str = None) -> list:
        """查询分析会话列表，可按八字筛选"""
        with self._conn() as conn:
            if bazi:
                rows = conn.execute(
                    "SELECT * FROM analysis_sessions WHERE bazi_input=? ORDER BY created_at DESC",
                    (bazi,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM analysis_sessions ORDER BY created_at DESC LIMIT 50"
                ).fetchall()
            return [dict(r) for r in rows]

    def get_session_conclusions(self, session_id: str) -> list:
        """获取某会话的所有结论"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM conclusions WHERE session_id=? ORDER BY book_name, sequence",
                (session_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_session_variants(self, session_id: str) -> list:
        """获取某会话的所有变体"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM variants WHERE session_id=?",
                (session_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_session_comparisons(self, session_id: str) -> list:
        """获取某会话的所有比对结果"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM comparison_results WHERE session_id=? ORDER BY relevance_score DESC",
                (session_id,)
            ).fetchall()
            return [dict(r) for r in rows]

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

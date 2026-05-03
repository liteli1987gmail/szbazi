"""
主 Agent 编排器
将四个 Node 串联为完整流程，管理状态和进度
"""
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, Optional

from .state.state import PipelineState
from .nodes import (
    BookAnalysisNode, VariantExpansionNode,
    ComparisonNode, SynthesisNode
)
from .llms.llm import BaseLLM, create_llm
from .llms.minimax import MiniMaxLLM
from .tools.database import BookDatabase

logger = logging.getLogger(__name__)


class BaziAgent:
    """
    八字分析主 Agent

    流程：
    1. 并行读取各书，每本书产出 N 条段落结论
    2. 所有结论展开为 2N 条对/错变体
    3. 2N 条变体遍历全书所有段落，并发比对
    4. 综合对/错两组结果，输出最终报告
    """

    def __init__(self, config, on_stage_change: Optional[Callable] = None):
        self.config = config
        self.on_stage_change = on_stage_change  # UI 阶段切换回调

        # 根据 LLM_TYPE 创建对应的 LLM
        llm_type = getattr(config, 'LLM_TYPE', 'OpenAI')
        if llm_type == 'MiniMax':
            from dotenv import load_dotenv
            load_dotenv()
            import os
            api_key = os.getenv("ANTHROPIC_API_KEY")
            base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
            model = getattr(config, 'OPENAI_MODEL', 'MiniMax-M2')
            self.llm = MiniMaxLLM(api_key=api_key, base_url=base_url, model=model)
        else:
            self.llm = create_llm(config)

        self.db = BookDatabase(config.DB_PATH)
        self.state: Optional[PipelineState] = None

    # ── 公开接口 ────────────────────────────────────────

    def analyze(self, bazi: str, progress_callbacks: Dict[str, Callable] = None) -> PipelineState:
        """
        执行完整分析流程，返回最终状态。

        progress_callbacks 格式：
        {
            "book": fn(book_name, done, total),
            "variant": fn(done, total),
            "comparison": fn(done, total),
        }
        """
        cbs = progress_callbacks or {}
        self.state = PipelineState(bazi_input=bazi)

        # ── Stage 1：并行读书，产出各书的 N 条结论 ────────
        self._notify("reading_books")
        books = self.db.get_all_books()
        if not books:
            raise ValueError("数据库中没有书籍，请先导入数据")

        with ThreadPoolExecutor(max_workers=self.config.MAX_PARALLEL_AGENTS) as pool:
            futures = {}
            for book in books:
                paragraphs = self.db.get_paragraphs_by_book(book["book_id"])

                def make_progress(bname):
                    def _cb(done, total, *_):
                        if "book" in cbs:
                            cbs["book"](bname, done, total)
                    return _cb

                node = BookAnalysisNode(self.llm, on_progress=make_progress(book["book_name"]))
                futures[pool.submit(node.run, bazi, paragraphs)] = book["book_id"]

            for fut in as_completed(futures):
                book_id = futures[fut]
                try:
                    conclusions = fut.result()
                    self.state.conclusions_by_book[book_id] = conclusions
                    logger.info(f"书 {book_id} 完成，得到 {len(conclusions)} 条结论")
                except Exception as e:
                    logger.error(f"书 {book_id} 分析失败: {e}")
                    self.state.conclusions_by_book[book_id] = []

        self.state.stage = "books_done"
        self._save_checkpoint("stage1_conclusions")

        # 汇总所有结论
        all_conclusions = [
            c for clist in self.state.conclusions_by_book.values() for c in clist
        ]
        logger.info(f"全部结论共 {len(all_conclusions)} 条（N={len(all_conclusions)}）")

        # ── Stage 2：展开 2N 变体 ─────────────────────────
        self._notify("expanding_variants")

        def variant_cb(done, total):
            if "variant" in cbs:
                cbs["variant"](done, total)

        expansion_node = VariantExpansionNode(self.llm, on_progress=variant_cb)
        self.state.variant_records = expansion_node.run(all_conclusions)
        logger.info(f"展开变体共 {len(self.state.variant_records)} 条（2N）")
        self.state.stage = "variants_done"
        self._save_checkpoint("stage2_variants")

        # ── Stage 3：2N × 全段落回溯比对 ─────────────────
        self._notify("comparing")
        all_paragraphs = self.db.get_all_paragraphs()

        def comparison_cb(done, total):
            if "comparison" in cbs:
                cbs["comparison"](done, total)

        comparison_node = ComparisonNode(
            llm=self.llm,
            min_relevance=0.5,
            max_workers=4,
            on_progress=comparison_cb,
        )
        self.state.correct_results, self.state.incorrect_results = comparison_node.run(
            self.state.variant_records, all_paragraphs
        )
        logger.info(
            f"比对完成：对组 {len(self.state.correct_results)} 条，"
            f"错组 {len(self.state.incorrect_results)} 条"
        )
        self.state.stage = "comparison_done"
        self._save_checkpoint("stage3_comparisons")

        # ── Stage 4：综合生成最终结论 ──────────────────────
        self._notify("synthesizing")
        synthesis_node = SynthesisNode(self.llm, top_n=10)
        self.state.final_conclusion = synthesis_node.run(
            bazi,
            self.state.correct_results,
            self.state.incorrect_results,
        )
        self.state.stage = "done"
        self._save_checkpoint("stage4_final")

        # 保存报告
        self._save_report(bazi)
        return self.state

    def get_progress_summary(self) -> Dict:
        if not self.state:
            return {"stage": "not_started"}
        return self.state.to_dict()

    # ── 私有方法 ────────────────────────────────────────

    def _notify(self, stage: str):
        self.state.stage = stage
        logger.info(f"▶ 阶段：{stage}")
        if self.on_stage_change:
            self.on_stage_change(stage)

    def _save_checkpoint(self, name: str):
        if not getattr(self.config, "SAVE_INTERMEDIATE_STATES", False):
            return
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
        path = os.path.join(self.config.OUTPUT_DIR, f"{name}.pkl")
        self.state.save(path)

    def _save_report(self, bazi: str):
        if not self.state.final_conclusion:
            return
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self.config.OUTPUT_DIR, f"report_{bazi}_{ts}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# 八字分析报告：{bazi}\n\n")
            f.write(self.state.final_conclusion.synthesis)
        logger.info(f"报告已保存：{path}")

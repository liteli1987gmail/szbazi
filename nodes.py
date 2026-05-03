"""
处理节点模块
每个 Node 负责流程中的一个阶段
"""
import json
import uuid
import time
import logging
from typing import List, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..state.state import (
    Paragraph, ParagraphConclusion, VariantRecord,
    ComparisonResult, FinalConclusion, VariantType, PipelineState
)
from ..prompts.prompts import (
    PARAGRAPH_ANALYSIS_SYSTEM, PARAGRAPH_ANALYSIS_USER,
    VARIANT_EXPANSION_SYSTEM, VARIANT_EXPANSION_USER,
    COMPARISON_SYSTEM, COMPARISON_USER,
    SYNTHESIS_SYSTEM, SYNTHESIS_USER,
)
from ..llms.llm import BaseLLM

logger = logging.getLogger(__name__)


def _safe_json(text: str) -> dict:
    """提取 LLM 返回中的 JSON，容错处理"""
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return {}


# ══════════════════════════════════════════════════════════
# Node 1：单本书的段落分析
# ══════════════════════════════════════════════════════════

class BookAnalysisNode:
    """
    逐段落读取一本书，分析每段与八字的关系，产出 N 条结论。
    对应流程图第一、二层。
    """
    def __init__(self, llm: BaseLLM, on_progress: Optional[Callable] = None):
        self.llm = llm
        self.on_progress = on_progress  # 进度回调，用于 Streamlit 实时更新

    def run(self, bazi: str, paragraphs: List[Paragraph]) -> List[ParagraphConclusion]:
        conclusions = []
        total = len(paragraphs)

        for idx, para in enumerate(paragraphs):
            if self.on_progress:
                self.on_progress(idx + 1, total, para.book_name, para.sequence)

            messages = [
                {"role": "system", "content": PARAGRAPH_ANALYSIS_SYSTEM},
                {"role": "user", "content": PARAGRAPH_ANALYSIS_USER.format(
                    bazi=bazi,
                    book_name=para.book_name,
                    sequence=para.sequence,
                    content=para.content,
                )},
            ]
            try:
                result = self.llm.chat(messages)
                if "无关" in result:
                    continue
                conclusions.append(ParagraphConclusion(
                    conclusion_id=str(uuid.uuid4()),
                    paragraph=para,
                    bazi_input=bazi,
                    conclusion_text=result,
                    created_at=time.time(),
                ))
            except Exception as e:
                logger.warning(f"段落分析失败 {para.paragraph_id}: {e}")

        return conclusions


# ══════════════════════════════════════════════════════════
# Node 2：展开 2N 变体
# ══════════════════════════════════════════════════════════

class VariantExpansionNode:
    """
    将所有书的 N 条结论各自展开为「对」和「错」两个变体，共 2N 条。
    对应流程图第三层。
    """
    def __init__(self, llm: BaseLLM, on_progress: Optional[Callable] = None):
        self.llm = llm
        self.on_progress = on_progress

    def run(self, conclusions: List[ParagraphConclusion]) -> List[VariantRecord]:
        variants = []
        total = len(conclusions)

        for idx, conc in enumerate(conclusions):
            if self.on_progress:
                self.on_progress(idx + 1, total)

            messages = [
                {"role": "system", "content": VARIANT_EXPANSION_SYSTEM},
                {"role": "user", "content": VARIANT_EXPANSION_USER.format(
                    bazi=conc.bazi_input,
                    conclusion=conc.conclusion_text,
                )},
            ]
            try:
                raw = self.llm.chat(messages)
                data = _safe_json(raw)
                for vtype in [VariantType.CORRECT, VariantType.INCORRECT]:
                    key = vtype.value
                    if key in data and data[key]:
                        variants.append(VariantRecord(
                            variant_id=str(uuid.uuid4()),
                            source_conclusion=conc,
                            variant_type=vtype,
                            variant_text=data[key],
                        ))
            except Exception as e:
                logger.warning(f"变体展开失败 {conc.conclusion_id}: {e}")

        return variants


# ══════════════════════════════════════════════════════════
# Node 3：回溯比对（2N × 全书段落）
# ══════════════════════════════════════════════════════════

class ComparisonNode:
    """
    将 2N 条变体记录与所有书的全部段落逐一比对，
    按对/错分组存储比对结果。
    对应流程图第四、五层。
    """
    def __init__(
        self,
        llm: BaseLLM,
        min_relevance: float = 0.5,  # 低于此分数的比对结果丢弃
        max_workers: int = 4,        # 并发线程数
        on_progress: Optional[Callable] = None,
    ):
        self.llm = llm
        self.min_relevance = min_relevance
        self.max_workers = max_workers
        self.on_progress = on_progress

    def _compare_one(self, variant: VariantRecord, para: Paragraph) -> Optional[ComparisonResult]:
        messages = [
            {"role": "system", "content": COMPARISON_SYSTEM},
            {"role": "user", "content": COMPARISON_USER.format(
                bazi=variant.source_conclusion.bazi_input,
                variant_type="对（正向）" if variant.variant_type == VariantType.CORRECT else "错（负向）",
                variant_text=variant.variant_text,
                book_name=para.book_name,
                sequence=para.sequence,
                content=para.content,
            )},
        ]
        raw = self.llm.chat(messages)
        data = _safe_json(raw)
        score = float(data.get("relevance_score", 0))
        if score < self.min_relevance:
            return None
        return ComparisonResult(
            result_id=str(uuid.uuid4()),
            variant_record=variant,
            compared_paragraph=para,
            relationship=data.get("relationship", "未知"),
            relevance_score=score,
        )

    def run(
        self,
        variants: List[VariantRecord],
        all_paragraphs: List[Paragraph],
    ) -> tuple[List[ComparisonResult], List[ComparisonResult]]:

        correct_results = []
        incorrect_results = []
        total = len(variants) * len(all_paragraphs)
        done = 0

        tasks = [(v, p) for v in variants for p in all_paragraphs]

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._compare_one, v, p): (v, p) for v, p in tasks}
            for fut in as_completed(futures):
                done += 1
                if self.on_progress:
                    self.on_progress(done, total)
                try:
                    result = fut.result()
                    if result is None:
                        continue
                    if result.variant_record.variant_type == VariantType.CORRECT:
                        correct_results.append(result)
                    else:
                        incorrect_results.append(result)
                except Exception as e:
                    v, p = futures[fut]
                    logger.warning(f"比对失败 variant={v.variant_id} para={p.paragraph_id}: {e}")

        # 按相关度降序排列
        correct_results.sort(key=lambda r: r.relevance_score, reverse=True)
        incorrect_results.sort(key=lambda r: r.relevance_score, reverse=True)
        return correct_results, incorrect_results


# ══════════════════════════════════════════════════════════
# Node 4：综合对比，生成最终结论
# ══════════════════════════════════════════════════════════

class SynthesisNode:
    """
    综合对组和错组的比对结果，输出最终命理分析报告。
    对应流程图第六层。
    """
    def __init__(self, llm: BaseLLM, top_n: int = 10):
        self.llm = llm
        self.top_n = top_n

    def _format_results(self, results: List[ComparisonResult]) -> str:
        lines = []
        for r in results[:self.top_n]:
            lines.append(
                f"- [{r.relationship}·{r.relevance_score:.2f}] "
                f"《{r.compared_paragraph.book_name}》第{r.compared_paragraph.sequence}段\n"
                f"  变体：{r.variant_record.variant_text}\n"
                f"  关系说明：{r.relationship}"
            )
        return "\n".join(lines) if lines else "（无高相关结果）"

    def run(
        self,
        bazi: str,
        correct_results: List[ComparisonResult],
        incorrect_results: List[ComparisonResult],
    ) -> FinalConclusion:
        messages = [
            {"role": "system", "content": SYNTHESIS_SYSTEM},
            {"role": "user", "content": SYNTHESIS_USER.format(
                bazi=bazi,
                top_n=self.top_n,
                correct_summary=self._format_results(correct_results),
                incorrect_summary=self._format_results(incorrect_results),
            )},
        ]
        synthesis = self.llm.chat(messages, temperature=0.5)
        return FinalConclusion(
            bazi_input=bazi,
            correct_comparisons=correct_results,
            incorrect_comparisons=incorrect_results,
            synthesis=synthesis,
        )

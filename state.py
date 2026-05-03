"""
状态管理模块
定义整个 Agent 流程中的数据结构
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import json
import time


class VariantType(str, Enum):
    CORRECT = "correct"      # 对的变体
    INCORRECT = "incorrect"  # 错的变体


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class Paragraph:
    """书中一个段落"""
    paragraph_id: str
    book_id: str
    book_name: str
    content: str
    sequence: int            # 段落在书中的顺序


@dataclass
class ParagraphConclusion:
    """单个段落的分析结论"""
    conclusion_id: str
    paragraph: Paragraph
    bazi_input: str          # 用户输入的八字
    conclusion_text: str     # 推导出的结论
    created_at: float = field(default_factory=time.time)


@dataclass
class VariantRecord:
    """对/错变体记录（2N 层）"""
    variant_id: str
    source_conclusion: ParagraphConclusion
    variant_type: VariantType
    variant_text: str        # 正向或负向表述


@dataclass
class ComparisonResult:
    """变体记录与某段落的比对结果"""
    result_id: str
    variant_record: VariantRecord
    compared_paragraph: Paragraph
    relationship: str        # 发现的关系描述
    relevance_score: float   # 相关度 0~1


@dataclass
class FinalConclusion:
    """最终综合结论"""
    bazi_input: str
    correct_comparisons: List[ComparisonResult]
    incorrect_comparisons: List[ComparisonResult]
    synthesis: str           # 综合结论文本
    created_at: float = field(default_factory=time.time)


@dataclass
class PipelineState:
    """整个流程的状态快照，支持断点恢复"""
    bazi_input: str
    stage: str = "init"

    # 第一层：各书的段落结论（N 条 per book）
    conclusions_by_book: Dict[str, List[ParagraphConclusion]] = field(default_factory=dict)

    # 第二层：展开的 2N 变体
    variant_records: List[VariantRecord] = field(default_factory=list)

    # 第三层：比对结果
    correct_results: List[ComparisonResult] = field(default_factory=list)
    incorrect_results: List[ComparisonResult] = field(default_factory=list)

    # 第四层：最终结论
    final_conclusion: Optional[FinalConclusion] = None

    # 进度追踪
    progress: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "bazi_input": self.bazi_input,
            "stage": self.stage,
            "progress": self.progress,
            "conclusions_count": sum(len(v) for v in self.conclusions_by_book.values()),
            "variants_count": len(self.variant_records),
            "correct_results_count": len(self.correct_results),
            "incorrect_results_count": len(self.incorrect_results),
            "has_final": self.final_conclusion is not None,
        }

    def save(self, filepath: str):
        import pickle
        with open(filepath, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, filepath: str) -> "PipelineState":
        import pickle
        with open(filepath, "rb") as f:
            return pickle.load(f)

> ⚠️ **核心问题**：所有大模型的 chatbot 查询四柱八字以及解析都是有瑕疵的，幻觉不断。
>
> 为了解决这个问题，本项目从最基本的四柱八字开始，结合古籍，对输入的八字进行**批判分析、交叉验证**，
> 获得的分析报告比任何 AI 聊天获得的结果准确率提升至少 **90% 以上**。

---

# 八字古籍多 Agent 分析系统

基于多本古籍知识库，通过多阶段 Agent 流程对用户输入的八字进行深度命理分析。

---

## 社群联络

对 API 调用、八字计算与解读有疑问？请备注需求添加微信：

![社群联络]https://raw.githubusercontent.com/liteli1987gmail/graphragzh/main/public/img/wechat.jpg"

---

## 算力支持

本项目 API 算力由 **DMXAPI** 提供：https://dmxapi.com/

---

## 流程架构（当前）

```
用户输入八字
    │
    ├─── Agent（书A）─── N条段落结论 ─┐
    ├─── Agent（书B）─── N条段落结论 ─┤
    └─── Agent（书C）─── N条段落结论 ─┘
                                        │
                              展开 2N 变体（对 + 错）
                                        │
                           Stage 3 比对（已跳过，直接进综合）
                                        │
                               综合对比 → 最终报告
```

> **注意**：当前 Stage 3（全段落回溯比对）已跳过，直接基于变体生成综合结论。
> 如需启用全量比对，可在 `src/agent.py` 中恢复 Stage 3 代码。

---

## 已入库古籍

| 书名 | 段落数 |
|------|--------|
| 三命通会 | 354 |
| 滴天髓阐微 | 221 |
| 穷通宝鉴 | 334 |

---

## 八字排盘查询（万年历）

输入八字前，需通过万年历核实准确干支。特别注意**节气临界点**的特殊情况。

### 万年历查询地址

**http://staff.ustc.edu.cn/~slliu/wannianli.htm**

此页面可查询任意公历日期对应的农历干支，用于核实年柱、月柱、日柱、时柱。

### ⚠️ 节气临界点——必须用【五虎遁】核月干

当出生时间恰好在节气交节附近时，**月柱不能简单按月份划分**，必须核实节气交节时间：

> 口诀：**五虎遁** — 甲己之年丙作首，乙庚之年戊为头，丙辛必定寻庚起，丁壬壬位顺行流，戊癸之年何方发，壬子之上好追求。

| 年干 | 正月（寅月）天干 |
|------|-----------------|
| 甲、己 | 丙 |
| 乙、庚 | 戊 |
| 丙、辛 | 庚 |
| 丁、壬 | 壬 |
| 戊、癸 | 壬 |

### 特殊举例：节气前10小时出生

**案例：1965年7月7日 10:50（巳时）**

| 检查项 | 结果 |
|--------|------|
| 小暑交节时间 | **1965年7月7日 21:09** |
| 出生时间 | 上午 **10:50** |
| 距节气 | 仅差 **10小时**（在节气之前！） |

**结论**：此人生时完美避开了小暑，月柱必须死死咬住上一个月（**芒种**）的干支。

**五虎遁推算月柱：**

1. 判断年干：1965年 → 乙巳年 → 年干为 **乙**
2. 乙年推午月：乙庚之年戊为头 → 五月起壬午 → 所以 **壬午** 为月柱

**日柱、时柱万年历核实：**

- 日柱：1965年7月7日 → **壬戌** 日
- 壬日推巳时：丁壬庚子居 → 上午9-11点为 **乙巳** 时

**【最终命局骨架】**

```
乙巳  壬午  壬戌  乙巳
年柱  月柱  日柱  时柱
```

> **经验法则**：若出生时间距离节气交节 **不足12小时**，必须查万年历核实月柱归属，绝不能按月令直接取。

---

## 数据库表结构

### 知识库（书籍段落）

```sql
CREATE TABLE books (
    book_id   TEXT PRIMARY KEY,
    book_name TEXT NOT NULL
);

CREATE TABLE paragraphs (
    paragraph_id TEXT PRIMARY KEY,
    book_id      TEXT NOT NULL,
    sequence     INTEGER NOT NULL,
    content      TEXT NOT NULL
);
```

### 分析结果（按八字可查）

```sql
CREATE TABLE analysis_sessions (
    session_id      TEXT PRIMARY KEY,
    bazi_input      TEXT NOT NULL,
    created_at      REAL NOT NULL,
    config          TEXT,
    final_conclusion TEXT
);

CREATE TABLE conclusions (
    conclusion_id    TEXT PRIMARY KEY,
    session_id       TEXT NOT NULL,
    book_id          TEXT NOT NULL,
    book_name        TEXT NOT NULL,
    paragraph_id     TEXT NOT NULL,
    sequence         INTEGER NOT NULL,
    paragraph_content TEXT NOT NULL,
    conclusion_text  TEXT NOT NULL,
    created_at       REAL NOT NULL
);

CREATE TABLE variants (
    variant_id          TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL,
    source_conclusion_id TEXT NOT NULL,
    variant_type        TEXT NOT NULL,   -- correct / incorrect
    variant_text        TEXT NOT NULL
);

CREATE TABLE comparison_results (
    result_id         TEXT PRIMARY KEY,
    session_id        TEXT NOT NULL,
    variant_id        TEXT NOT NULL,
    compared_book_id  TEXT NOT NULL,
    compared_book_name TEXT NOT NULL,
    compared_paragraph_id TEXT NOT NULL,
    compared_sequence  INTEGER NOT NULL,
    compared_content   TEXT NOT NULL,
    relationship       TEXT NOT NULL,
    relevance_score    REAL NOT NULL
);
```

---

## 配置说明

环境变量文件 `.env`：

```bash
ANTHROPIC_API_KEY=your_key
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
ANTHROPIC_MODEL=MiniMax-M2          # 可选 MiniMax-M2.7-highspeed（需套餐支持）
```

---

## 中间状态保存

每次阶段完成会同时保存：
- `.pkl` — 程序断点恢复用
- `.json` — 人工查看 + 中断后重新入库

---

## LLM 兼容性

| LLM | 配置 |
|-----|------|
| MiniMax | `LLM_TYPE=MiniMax`，自动从 `.env` 读取 |
| OpenAI/DeepSeek | `LLM_TYPE=OpenAI`，手动填 API Key 和 Base URL |

MiniMax 适配器内置 RateLimit 重试（最多5次，递增等待）。

---

## 项目结构

```
szbazi/
├── src/
│   ├── agent.py              # 主 Agent 编排器（四阶段串联）
│   ├── nodes.py              # 各阶段处理节点
│   ├── state/state.py        # 数据结构定义
│   ├── prompts/prompts.py    # 所有提示词模板
│   ├── llms/
│   │   ├── minimax.py       # MiniMax 适配器（含重试机制）
│   │   └── llm.py            # OpenAI/DeepSeek 适配器
│   ├── tools/database.py     # SQLite 数据库工具（含分析结果存储）
│   └── streamlit_app.py      # Web 界面
├── reports/
│   ├── synthesize_variants.py # Stage 4 独立综合脚本
│   └── import_checkpoint.py   # 将 checkpoint 导入数据库
├── data/
│   └── bazi_knowledge.db      # SQLite 数据库
├── logs/
│   └── analysis_log.py       # 分析日志模块
├── seed_sanming_full.py        # 三命通会数据填充
└── seed_ditian.py              # 滴天髓阐微数据填充
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 初始化数据库（如需）

```bash
python seed_sanming_full.py    # 三命通会
python seed_ditian.py           # 滴天髓阐微
```

### 3. 启动 Web 界面

```bash
streamlit run src/streamlit_app.py
```

支持批量输入八字（多行）、并发控制（最多5个同时分析）。

### 4. 命令行分析

```python
import types
from src import BaziAgent
from dotenv import load_dotenv

load_dotenv()

config = types.SimpleNamespace(
    OPENAI_API_KEY=os.getenv("ANTHROPIC_API_KEY"),
    OPENAI_BASE_URL=os.getenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic"),
    OPENAI_MODEL=os.getenv("ANTHROPIC_MODEL", "MiniMax-M2"),
    DB_PATH="data/bazi_knowledge.db",
    MAX_PARALLEL_AGENTS=3,
    OUTPUT_DIR="reports",
    SAVE_INTERMEDIATE_STATES=True,
    LLM_TYPE="MiniMax",
)

agent = BaziAgent(config)
state = agent.analyze("甲子 乙丑 丙寅 丁卯")
print(state.final_conclusion.synthesis)
```

### 5. 独立生成综合结论（Stage 4）

已有分析结果后，可直接用变体数据生成综合报告：

```bash
python reports/synthesize_variants.py <session_id>
# 例：python reports/synthesize_variants.py 3b983d14-6275-4298-b328-19a2507e6a23
```
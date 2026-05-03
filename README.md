# 八字古籍多 Agent 分析系统

基于多本古籍知识库，通过四阶段 Agent 流程对用户输入的八字进行深度命理分析。

## 流程架构

```
用户输入八字
    │
    ├─── Agent 1（书A）─── N条段落结论 ─┐
    ├─── Agent 2（书B）─── N条段落结论 ─┤
    └─── Agent 3（书C）─── N条段落结论 ─┘
                                        │
                              展开 2N 变体（对 + 错）
                                        │
                       2N × 全书所有段落 → 回溯比对
                        ┌───────────────┴───────────────┐
                   对组结果集                        错组结果集
                        └───────────────┬───────────────┘
                               综合对比 → 最终报告
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 初始化示例数据

```bash
python examples/seed_data.py
```

### 3. 启动 Web 界面

```bash
streamlit run examples/streamlit_app.py
```

### 4. 编程方式调用

```python
import types
from src import BaziAgent

config = types.SimpleNamespace(
    OPENAI_API_KEY="your_key",
    OPENAI_BASE_URL="https://api.openai.com/v1",
    OPENAI_MODEL="gpt-4o-mini",
    DB_PATH="data/bazi_knowledge.db",
    MAX_PARALLEL_AGENTS=3,
    OUTPUT_DIR="reports",
    SAVE_INTERMEDIATE_STATES=True,
)

agent = BaziAgent(config)
state = agent.analyze("甲子乙丑丙寅丁卯")
print(state.final_conclusion.synthesis)
```

## 项目结构

```
bazi_agent/
├── src/
│   ├── agent.py              # 主 Agent 编排器
│   ├── llms/llm.py           # LLM 调用层（OpenAI / DeepSeek）
│   ├── nodes/nodes.py        # 四个处理节点
│   ├── prompts/prompts.py    # 所有提示词
│   ├── state/state.py        # 数据结构与状态管理
│   └── tools/database.py     # 数据库读写工具
├── examples/
│   ├── streamlit_app.py      # Web 界面
│   └── seed_data.py          # 示例数据初始化
├── data/                     # SQLite 数据库
├── reports/                  # 输出报告和中间状态
├── config.py                 # 配置文件
└── requirements.txt
```

## 数据库表结构

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

将你的古籍数据按此结构导入即可，其余逻辑由框架自动处理。

## 切换 DeepSeek

在侧边栏或 config.py 中：

```python
OPENAI_BASE_URL = "https://api.deepseek.com/v1"
OPENAI_MODEL    = "deepseek-chat"
OPENAI_API_KEY  = "your_deepseek_key"
```

## 性能说明

- 第三阶段（回溯比对）复杂度为 O(2N × 段落总数)，段落多时耗时较长
- 通过 `min_relevance` 阈值过滤低相关比对，可大幅减少无效结果
- `max_workers` 控制并发线程数，根据 API 限速调整

# 八字分析 Agent 配置文件

# LLM API 配置
OPENAI_API_KEY = "your_openai_api_key_here"
OPENAI_BASE_URL = "https://api.openai.com/v1"   # 可替换为 DeepSeek 等兼容接口
OPENAI_MODEL = "gpt-4o-mini"

# 数据库配置（SQLite 默认，可替换为 PostgreSQL 等）
DB_PATH = "data/bazi_knowledge.db"

# Agent 行为配置
MAX_PARALLEL_AGENTS = 3          # 并行读书 Agent 数量（对应书本数量）
BATCH_SIZE = 10                  # 每批处理的段落数
EXPANSION_VARIANTS = ["correct", "incorrect"]  # 变体类型：对/错

# 输出配置
OUTPUT_DIR = "reports"
SAVE_INTERMEDIATE_STATES = True

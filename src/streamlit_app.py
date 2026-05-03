"""
Streamlit Web 界面
提供八字输入、实时进度展示、结果可视化
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import threading
import time
import types
from dotenv import load_dotenv

load_dotenv()

# 导入日志模块
from logs.analysis_log import save_analysis_log, list_analysis_logs

# ── 状态初始化 ─────────────────────────────────────────
if "job_queue" not in st.session_state:
    st.session_state["job_queue"] = []
if "active_jobs" not in st.session_state:
    st.session_state["active_jobs"] = {}  # job_id -> progress_state

if "completed_count" not in st.session_state:
    st.session_state["completed_count"] = 0

# ── 页面配置 ──────────────────────────────────────────
st.set_page_config(
    page_title="八字古籍分析系统",
    page_icon="☯",
    layout="wide",
)

st.title("☯ 八字古籍多Agent分析系统")
st.caption("基于多本古籍，逐段落分析八字命理，2N变体回溯比对，综合得出结论")

# ── 侧边栏：配置 ───────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 系统配置")

    # LLM 类型选择
    llm_type = st.selectbox("LLM 类型", ["MiniMax", "OpenAI/DeepSeek"])

    if llm_type == "MiniMax":
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
        model = "MiniMax-M2"
        st.success(f"✅ 使用 MiniMax（自动读取 .env）")
    else:
        api_key = st.text_input("API Key", type="password")
        base_url = st.text_input("API Base URL", value="https://api.openai.com/v1")
        model = st.selectbox("模型", ["gpt-4o-mini", "gpt-4o", "deepseek-chat"])

    db_path = st.text_input("数据库路径", value="data/bazi_knowledge.db")

    st.divider()
    st.header("🔧 Agent 参数")
    max_agents = st.slider("并行 Agent 数（书本数）", 1, 8, 3)
    min_relevance = st.slider("最低相关度阈值", 0.0, 1.0, 0.5, 0.05)
    top_n = st.slider("最终综合取用 Top-N 结果", 5, 20, 10)
    max_workers = st.slider("比对并发线程数", 1, 8, 4)

    st.divider()
    st.header("📜 分析日志")
    if st.button("🔄 刷新日志列表"):
        st.rerun()
    logs = list_analysis_logs()
    if logs:
        for log in logs[:10]:
            st.text(f"{log['timestamp']} | {log['bazi']} | {log['conclusions_count']}条")
    else:
        st.info("暂无分析日志")

    st.divider()
    st.info("💡 比对阶段耗时较长（2N × 全段落），建议先用小数据集测试")

# ── 主区域 ────────────────────────────────────────────
col_input, col_status = st.columns([1, 1])

with col_input:
    st.subheader("📥 输入八字（支持批量，每行一个）")
    bazi_input = st.text_area(
        "八字列表",
        placeholder="甲子 乙丑\n丙寅 丁卯\n戊辰 己巳",
        height=150,
    )
    max_concurrent = st.slider("并发分析数", 1, 5, 2, key="_max_concurrent")

    if st.button("🚀 加入分析队列", type="primary"):
        bazi_list = [b.strip() for b in bazi_input.strip().split("\n") if b.strip()]
        if not bazi_list:
            st.error("请输入至少一个八字")
        else:
            for bazi in bazi_list:
                job_id = f"{bazi.replace(' ', '')}_{int(time.time() * 1000)}"
                job_state = {
                    "job_id": job_id,
                    "bazi": bazi,
                    "status": "queued",
                    "stage": "",
                    "progress": 0.0,
                    "error": None,
                    "result_state": None,
                }
                st.session_state["job_queue"].append(job_state)
            st.success(f"已加入 {len(bazi_list)} 个八字到分析队列")
            st.rerun()

    # 显示队列状态
    if st.session_state.get("job_queue"):
        st.divider()
        st.subheader("📋 分析队列")
        for i, job in enumerate(st.session_state["job_queue"]):
            icon = {"queued": "⏳", "running": "🔄", "done": "✅", "error": "❌"}.get(job["status"], "❓")
            st.text(f"{icon} {job['bazi']} — {job['status']} {job['stage'] or ''}")

with col_status:
    st.subheader("📊 实时进度")
    for job in st.session_state["job_queue"]:
        if job["status"] == "running":
            ps = st.session_state["active_jobs"].get(job["job_id"], {})
            stage = ps.get("stage", "init")
            label = STAGE_LABELS.get(stage, stage)
            st.markdown(f"**{job['bazi']}** — {label}")
            if ps.get("book_progress"):
                for bname, (done, total) in ps["book_progress"].items():
                    pct = done / total if total else 0
                    st.progress(pct, text=f"  {bname}：{done}/{total}")
            vd, vt = ps.get("variant_done", 0), ps.get("variant_total", 0)
            if vt > 0:
                st.progress(vd / vt, text=f"变体：{vd}/{vt}")
            cd, ct = ps.get("comparison_done", 0), ps.get("comparison_total", 0)
            if ct > 0:
                st.progress(cd / ct, text=f"比对：{cd}/{ct}")
            if ps.get("error"):
                st.error(f"错误：{ps['error']}")
    st.text(f"✅ 已完成: {st.session_state.get('completed_count', 0)} 个")

# ── 结果展示区 ────────────────────────────────────────
st.divider()
result_area = st.empty()
detail_tabs_placeholder = st.empty()


# ── 批量并发运行逻辑 ─────────────────────────────────
pending = [j for j in st.session_state["job_queue"] if j["status"] == "queued"]
running = [j for j in st.session_state["job_queue"] if j["status"] == "running"]

# 启动新任务（不超过并发上限）
while len(running) < st.session_state["_max_concurrent"] and pending:
    job = pending.pop(0)
    job["status"] = "running"
    running.append(job)
    # 初始化进度状态
    st.session_state["active_jobs"][job["job_id"]] = {
        "stage": "init",
        "book_progress": {},
        "variant_done": 0, "variant_total": 0,
        "comparison_done": 0, "comparison_total": 0,
        "error": None,
        "result_state": None,
    }

# 实时轮询所有运行中的任务
for job in running:
    ps = st.session_state["active_jobs"][job["job_id"]]

    def run_agent(job_id, bazi_val):
        try:
            config = types.SimpleNamespace(
                OPENAI_API_KEY=api_key,
                OPENAI_BASE_URL=base_url,
                OPENAI_MODEL=model,
                DB_PATH=db_path,
                MAX_PARALLEL_AGENTS=max_agents,
                MAX_WORKERS=max_workers,
                OUTPUT_DIR="reports",
                SAVE_INTERMEDIATE_STATES=True,
                LLM_TYPE=llm_type,
            )

            agent = BaziAgent(config, on_stage_change=lambda s, jid=job_id: st.session_state["active_jobs"][jid].update({"stage": s}))

            def book_cb(bname, done, total):
                st.session_state["active_jobs"][job_id]["book_progress"][bname] = (done, total)

            def variant_cb(done, total):
                st.session_state["active_jobs"][job_id].update({"variant_done": done, "variant_total": total})

            def comparison_cb(done, total):
                st.session_state["active_jobs"][job_id].update({"comparison_done": done, "comparison_total": total})

            state = agent.analyze(
                bazi_val,
                progress_callbacks={
                    "book": book_cb,
                    "variant": variant_cb,
                    "comparison": comparison_cb,
                },
            )
            st.session_state["active_jobs"][job_id]["result_state"] = state
        except Exception as e:
            st.session_state["active_jobs"][job_id]["error"] = str(e)

    # 在后台线程运行
    t = threading.Thread(target=run_agent, args=(job["job_id"], job["bazi"]), daemon=True)
    t.start()
    job["thread"] = t

# 检查完成情况
still_running = []
for job in running:
    ps = st.session_state["active_jobs"][job["job_id"]]
    if ps.get("result_state") or ps.get("error"):
        if ps.get("result_state") and ps.get("stage") == "done":
            job["status"] = "done"
            # 保存最终结论到 session
            state = ps["result_state"]
            all_c = [c for clist in state.conclusions_by_book.values() for c in clist]
            log_id, json_path, md_path = save_analysis_log(
                bazi=job["bazi"].strip(),
                conclusions=all_c,
                variant_records=state.variant_records,
                correct_results=state.correct_results,
                incorrect_results=state.incorrect_results,
                final_conclusion=state.final_conclusion.synthesis if state.final_conclusion else None,
                config={
                    "llm_type": llm_type,
                    "model": model if llm_type != "MiniMax" else "MiniMax-M2",
                    "db_path": db_path,
                    "max_agents": max_agents,
                }
            )
            st.session_state["completed_count"] += 1
        elif ps.get("error"):
            job["status"] = "error"
            job["error"] = ps["error"]
        else:
            still_running.append(job)
    elif job.get("thread") and job["thread"].is_alive():
        still_running.append(job)
    else:
        still_running.append(job)

running = still_running
st.session_state["job_queue"] = (
    [j for j in st.session_state["job_queue"] if j["status"] == "queued"] +
    running +
    [j for j in st.session_state["job_queue"] if j["status"] in ("done", "error")]
)

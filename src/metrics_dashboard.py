"""RAG 指标面板 — Streamlit 页面。

展示 data/rag_logs/ 下的查询日志统计数据，
包括耗时分布、检索数趋势、rerank/web_search 触发率等。
"""

from pathlib import Path
from datetime import UTC, datetime, timedelta
import json

import streamlit as st
import altair as alt
import pandas as pd

from config.settings import ROOT_DIR

_LOG_DIR = ROOT_DIR / "data" / "rag_logs"
_REPORT_DIR = ROOT_DIR / "data" / "eval_reports"


@st.cache_data(ttl=10)
def load_logs() -> pd.DataFrame:
    """Load all JSONL log files into a DataFrame."""
    records = []
    if _LOG_DIR.exists():
        for f in sorted(_LOG_DIR.glob("rag_*.jsonl")):
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
    df = pd.DataFrame(records)
    if not df.empty and "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["date"] = df["timestamp"].dt.date
    return df


@st.cache_data(ttl=60)
def load_eval_reports() -> pd.DataFrame:
    """Load evaluation report summaries."""
    records = []
    if _REPORT_DIR.exists():
        for f in sorted(_REPORT_DIR.glob("eval_*.json")):
            with open(f, encoding="utf-8") as fh:
                try:
                    data = json.load(fh)
                    summary = data.get("summary", {})
                    summary["_file"] = f.name
                    records.append(summary)
                except (json.JSONDecodeError, KeyError):
                    pass
    return pd.DataFrame(records)


def show():
    col_title, col_back = st.columns([3, 1])
    with col_title:
        st.subheader("📊 指标面板")
    with col_back:
        if st.button("← 返回对话", use_container_width=True):
            st.session_state.show_dashboard = False
            st.rerun()

    df = load_logs()
    eval_df = load_eval_reports()

    if df.empty:
        st.info("暂无查询日志数据。使用知识库问答后数据会自动记录到 data/rag_logs/。")
        return

    # ---------- KPI 卡片 ----------
    total = len(df)
    today = df[df["date"] == datetime.now(UTC).date()] if "date" in df.columns else pd.DataFrame()
    today_count = len(today)
    avg_ms = int(df["elapsed_ms"].mean()) if "elapsed_ms" in df.columns else 0
    fail_rate = 0
    if "quality_ok" in df.columns and total > 0:
        fail_rate = (1 - df["quality_ok"].astype(float).mean()) * 100

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("总查询次数", total, delta=f"今日 +{today_count}")
    col2.metric("平均耗时", f"{avg_ms}ms")
    col3.metric("质量失败率", f"{fail_rate:.1f}%")
    col4.metric("日志天数", df["date"].nunique() if "date" in df.columns else 0)

    st.divider()

    # ---------- 耗时分布 ----------
    if "elapsed_ms" in df.columns:
        st.markdown("#### 查询耗时分布")
        c1, c2 = st.columns(2)
        with c1:
            # Histogram
            hist = (
                alt.Chart(df)
                .mark_bar(opacity=0.7, color="#4C78A8")
                .encode(
                    alt.X("elapsed_ms:Q", bin=alt.Bin(maxbins=30), title="耗时 (ms)"),
                    alt.Y("count()", title="查询数"),
                )
                .properties(height=250)
            )
            st.altair_chart(hist, use_container_width=True)

        with c2:
            # Percentile table
            p50 = df["elapsed_ms"].quantile(0.50)
            p90 = df["elapsed_ms"].quantile(0.90)
            p95 = df["elapsed_ms"].quantile(0.95)
            p99 = df["elapsed_ms"].quantile(0.99)
            st.dataframe(
                pd.DataFrame([
                    {"分位": "P50", "耗时 (ms)": int(p50)},
                    {"分位": "P90", "耗时 (ms)": int(p90)},
                    {"分位": "P95", "耗时 (ms)": int(p95)},
                    {"分位": "P99", "耗时 (ms)": int(p99)},
                ]),
                hide_index=True,
                use_container_width=True,
            )

    # ---------- 耗时趋势 ----------
    if "date" in df.columns:
        st.divider()
        st.markdown("#### 每日趋势")
        daily = df.groupby("date").agg(
            查询量=("elapsed_ms", "count"),
            平均耗时=("elapsed_ms", "mean"),
        ).reset_index()
        daily["平均耗时"] = daily["平均耗时"].astype(int)

        base = alt.Chart(daily).encode(alt.X("date:T", title="日期"))

        line1 = base.mark_line(color="#4C78A8", point=True).encode(
            alt.Y("查询量:Q", title="查询次数"),
        ).properties(height=200)

        line2 = base.mark_line(color="#E45756", point=True).encode(
            alt.Y("平均耗时:Q", title="平均耗时 (ms)"),
        ).properties(height=200)

        st.altair_chart(line1, use_container_width=True)
        st.altair_chart(line2, use_container_width=True)

    # ---------- 质量与检索 ----------
    st.divider()
    st.markdown("#### 质量与检索")

    left, right = st.columns(2)
    with left:
        if "quality_ok" in df.columns:
            quality_counts = df["quality_ok"].value_counts().reset_index()
            quality_counts.columns = ["结果", "数量"]
            quality_counts["结果"] = quality_counts["结果"].map({True: "通过", False: "失败"})
            pie = (
                alt.Chart(quality_counts)
                .mark_arc(innerRadius=40)
                .encode(
                    theta="数量:Q",
                    color=alt.Color("结果:N", scale=alt.Scale(
                        domain=["通过", "失败"],
                        range=["#4C78A8", "#E45756"],
                    )),
                )
                .properties(height=250)
            )
            st.altair_chart(pie, use_container_width=True)

    with right:
        if "retrieval_count" in df.columns:
            ret_hist = (
                alt.Chart(df)
                .mark_bar(opacity=0.7, color="#54A24B")
                .encode(
                    alt.X("retrieval_count:Q", bin=alt.Bin(maxbins=10), title="检索文档数"),
                    alt.Y("count()", title="查询数"),
                )
                .properties(height=250)
            )
            st.altair_chart(ret_hist, use_container_width=True)

    # ---------- 最近查询 ----------
    st.divider()
    st.markdown("#### 最近查询")
    display_cols = [c for c in ["timestamp", "question", "elapsed_ms", "quality_ok", "retrieval_count", "quality_reason"] if c in df.columns]
    if display_cols:
        recent = df.sort_values("timestamp", ascending=False).head(20)[display_cols]
        recent["timestamp"] = recent["timestamp"].dt.strftime("%H:%M:%S")
        st.dataframe(recent, hide_index=True, use_container_width=True)

    # ---------- 离线评估报告 ----------
    st.divider()
    st.markdown("#### 离线评估报告")

    if eval_df.empty:
        st.info("暂无评估报告。运行 `uv run python -m src.evaluate` 生成。")
    else:
        for _, row in eval_df.iterrows():
            metrics = row.get("metrics", {})
            with st.expander(f"📋 {row.get('_file', '报告')} — {row.get('total_cases', '?')} 用例 — 平均 {row.get('avg_elapsed_ms', '?')}ms"):
                c1, c2 = st.columns(2)
                with c1:
                    st.write("**概览**")
                    st.write(f"- 用例: {row.get('total_cases', '?')} 通过: {row.get('passed_cases', '?')} 失败: {row.get('failed_cases', '?')}")
                    st.write(f"- 平均耗时: {row.get('avg_elapsed_ms', '?')}ms")
                with c2:
                    st.write("**指标**")
                    if isinstance(metrics, dict):
                        for mname, mdata in metrics.items():
                            st.write(f"- {mname}: avg={mdata.get('avg_score', '?')} pass={mdata.get('pass_rate', '?')}")

    # ---------- 原始日志 ----------
    with st.expander("📝 原始日志"):
        st.dataframe(df.tail(100), hide_index=True, use_container_width=True)


if __name__ == "__main__":
    st.set_page_config(page_title="KnowBase 指标", layout="wide")
    show()

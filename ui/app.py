"""
Streamlit UI — REST-only communication with backend.
No direct DB, no Redis, no sklearn imports.
"""
import os, time, json
import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
POLL_INTERVAL = 2    # seconds between status polls
MAX_POLLS = 60       # give up after ~2 min

st.set_page_config(page_title="AI Error Assistant", page_icon="🔍", layout="wide")


# ── REST helpers ──────────────────────────────────────────────────────────────
def api_get(path: str):
    """GET with graceful degradation — never shows a Python traceback."""
    try:
        r = httpx.get(f"{API_BASE}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        st.error(f"API error {e.response.status_code}: {e.response.text}")
    except Exception:
        st.error("🔴 Service temporarily unavailable. Please try again shortly.")
    return None


def api_post(path: str, payload: dict):
    try:
        r = httpx.post(f"{API_BASE}{path}", json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        st.error(f"API error {e.response.status_code}: {e.response.text}")
    except Exception:
        st.error("🔴 Service temporarily unavailable. Please try again shortly.")
    return None


# ── Analyze page ──────────────────────────────────────────────────────────────
def page_analyze():
    st.title("🔍 Error Analyzer")
    st.caption("Paste an error log or stack trace — the ML model will classify it asynchronously.")

    source = st.text_input("Source system", value="backend", max_chars=100)
    text = st.text_area("Error / Log text", height=220, max_chars=10_000,
                        placeholder="NullPointerException at com.example.Service:42")

    if st.button("🚀 Analyze", type="primary"):
        if len(text.strip()) < 10:
            st.warning("Enter at least 10 characters.")
            return

        # 202 Accepted — task enqueued
        with st.spinner("Submitting..."):
            resp = api_post("/api/analyze", {"text": text, "source": source})
        if not resp:
            return

        task_id = resp["task_id"]
        st.info(f"Task enqueued: `{task_id}`")

        # Poll until success / failure / timeout
        bar = st.progress(0, text="Waiting for ML worker…")
        result = None

        for i in range(MAX_POLLS):
            time.sleep(POLL_INTERVAL)
            sr = api_get(f"/api/tasks/{task_id}")
            if not sr:
                break
            bar.progress(min(int((i + 1) / MAX_POLLS * 100), 95),
                         text=f"Status: {sr['status']}…")
            if sr["status"] == "success":
                result = sr["result"]
                break
            if sr["status"] == "failure":
                st.error(f"Task failed: {sr.get('error', 'unknown')}")
                break

        if result:
            bar.progress(100, text="Done!")
            _render_result(result)
        elif result is None and i == MAX_POLLS - 1:
            st.warning("Timed out. Check History later.")


def _render_result(r: dict):
    icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
    icon = icons.get(r["severity"], "⚪")

    st.success("Analysis complete!")
    c1, c2, c3 = st.columns(3)
    c1.metric("Category", r["category"].replace("_", " ").title())
    c2.metric("Severity", f"{icon} {r['severity'].upper()}")
    c3.metric("Confidence", f"{r['confidence']:.0%}")

    st.subheader("Explanation")
    st.write(r["explanation"])

    st.subheader("Recommendations")
    for rec in r["recommendations"]:
        st.markdown(f"- {rec}")

    # Plotly confidence bar — satisfies "Visual representation" criterion
    fig = px.bar(
        x=["Confidence"], y=[r["confidence"] * 100],
        color_discrete_sequence=["#4CAF50" if r["confidence"] > 0.7 else "#FF9800"],
        labels={"y": "Confidence %", "x": ""},
        title="Model Confidence",
    )
    fig.update_layout(yaxis_range=[0, 100], height=240)
    st.plotly_chart(fig, use_container_width=True)


# ── History page ──────────────────────────────────────────────────────────────
def page_history():
    st.title("📋 Analysis History")
    data = api_get("/api/history?limit=100")
    if data is None:
        return
    if not data:
        st.info("No analyses yet. Go to Analyze to get started.")
        return

    df = pd.DataFrame(data)
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["confidence_pct"] = (df["confidence"] * 100).round(1)

    c1, c2 = st.columns(2)
    with c1:
        cats = df["category"].value_counts().reset_index()
        cats.columns = ["category", "count"]
        st.plotly_chart(
            px.pie(cats, values="count", names="category", title="Error Categories"),
            use_container_width=True,
        )
    with c2:
        sevs = df["severity"].value_counts().reset_index()
        sevs.columns = ["severity", "count"]
        st.plotly_chart(
            px.bar(sevs, x="severity", y="count", title="Severity Distribution",
                   color="severity",
                   color_discrete_map={"critical":"red","high":"orange","medium":"gold","low":"green"}),
            use_container_width=True,
        )

    st.plotly_chart(
        px.scatter(df, x="created_at", y="confidence_pct", color="category",
                   size="confidence_pct", title="Confidence Over Time",
                   labels={"confidence_pct":"Confidence %","created_at":"Time"}),
        use_container_width=True,
    )

    st.subheader("Records")
    st.dataframe(
        df[["id","created_at","source","category","severity","confidence_pct"]],
        use_container_width=True,
    )


# ── Navigation ────────────────────────────────────────────────────────────────
page = st.sidebar.radio("Navigation", ["🔍 Analyze", "📋 History"])

health = api_get("/api/health")
model_status = health.get('model', '?')
if health:
    icon = "🟢" if health["status"] == "ok" else "🟡"
    st.sidebar.markdown(f"**API:** {icon} {health['status']}  \n**Model:** {model_status}")
else:
    st.sidebar.markdown("**API:** 🔴 offline")

if page == "🔍 Analyze":
    page_analyze()
else:
    page_history()

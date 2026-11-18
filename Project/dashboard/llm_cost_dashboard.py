"""LLM Cost Dashboard — real-time API key health, token usage, and cost estimates."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from config import config
from dashboard.api_client import call_service
from dashboard.ui import (badge_html, callout, empty_state, escape,
                           page_header, section, spacer, stat_row)

_STATS_FILE = Path("database/api_key_stats.json")


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_router_stats() -> list[dict]:
    """Load API key stats from the router (live singleton or file fallback)."""
    try:
        from agentic.api_key_router import get_router
        return get_router().get_all_stats()
    except Exception:
        pass
    # Fallback: read raw JSON
    if _STATS_FILE.exists():
        try:
            raw = json.loads(_STATS_FILE.read_text())
            if isinstance(raw, dict):
                result = []
                for idx, (key, stat) in enumerate(raw.items(), 1):
                    stat = dict(stat)
                    stat["key_index"] = idx
                    stat["key_label"] = f"Key {idx}"
                    stat["key_preview"] = key[:8] + "…" if len(key) > 8 else key
                    result.append(stat)
                return result
        except Exception:
            pass
    return []


def _get_all_llm_calls() -> list[dict]:
    """Fetch call records for every available review from the API."""
    calls: list[dict] = []
    try:
        reviews = call_service(
            "GET", "/reviews",
            query={"status_value": config.REVIEW_STATUS_OPTIONS},
        )
        for review in reviews:
            try:
                budget = call_service("GET", f"/reviews/{review['review_id']}/calls")
                for call in budget.get("calls", []):
                    call["review_id"] = review["review_id"]
                    calls.append(call)
            except Exception:
                pass
    except Exception:
        pass
    return calls


def _cost_usd(prompt_tokens: int, response_tokens: int) -> float:
    return (
        prompt_tokens / 1_000_000 * config.GEMINI_INPUT_COST_PER_MILLION
        + response_tokens / 1_000_000 * config.GEMINI_OUTPUT_COST_PER_MILLION
    )


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------

def _render_key_health(stats: list[dict]) -> None:
    section("API Key Health", "Live status of every key in the routing pool.")
    if not stats:
        empty_state("No API keys configured", "Add GEMINI_API_KEY1 … GEMINI_API_KEY5 to .env")
        return

    rows = []
    for s in stats:
        status = s.get("status", "unknown")
        status_emoji = {"healthy": "🟢 Healthy", "cooldown": "🟡 Cooldown", "failed": "🔴 Failed"}.get(
            status, "⚪ Unknown"
        )
        cooldown_rem = s.get("cooldown_remaining", 0)
        cooldown_str = f"{cooldown_rem}s" if cooldown_rem else "—"
        tokens_hour = s.get("tokens_this_hour", 0)
        total_tok = s.get("total_tokens", 0)
        prompt_tok = s.get("total_prompt_tokens", 0)
        resp_tok = s.get("total_response_tokens", 0)
        total_calls = s.get("total_calls", 0)
        consec_fail = s.get("consecutive_failures", 0)
        est_cost = _cost_usd(prompt_tok, resp_tok)
        rows.append({
            "Key": s.get("key_label", f"Key {s.get('key_index', '?')}"),
            "Preview": s.get("key_preview", "…"),
            "Status": status_emoji,
            "Tokens / Hour": tokens_hour,
            "Total Tokens": total_tok,
            "Total Calls": total_calls,
            "Failures": consec_fail,
            "Cooldown": cooldown_str,
            "Est. Cost (USD)": f"${est_cost:.4f}",
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Tokens / Hour": st.column_config.NumberColumn(format="%d"),
            "Total Tokens": st.column_config.NumberColumn(format="%d"),
            "Total Calls": st.column_config.NumberColumn(format="%d", width="small"),
            "Failures": st.column_config.NumberColumn(format="%d", width="small"),
        },
    )

    # Visual health bar
    total = len(stats)
    healthy = sum(1 for s in stats if s.get("status") == "healthy")
    cooldown_count = sum(1 for s in stats if s.get("status") == "cooldown")
    failed_count = sum(1 for s in stats if s.get("status") == "failed")

    st.markdown(
        f"""
<div style="display:flex;gap:8px;align-items:center;margin-top:12px;flex-wrap:wrap">
  <span style="font-size:13px;color:var(--pw-muted)">Pool health:</span>
  {''.join(
      f'<span style="display:inline-flex;align-items:center;gap:5px;padding:4px 12px;'
      f'border-radius:20px;font-size:12.5px;font-weight:600;'
      f'background:{"rgba(22,163,74,0.12)" if s.get("status")=="healthy" else "rgba(202,138,4,0.12)" if s.get("status")=="cooldown" else "rgba(220,38,38,0.12)"};'
      f'color:{"#16a34a" if s.get("status")=="healthy" else "#ca8a04" if s.get("status")=="cooldown" else "#dc2626"}">'
      f'{"●" if s.get("status")=="healthy" else "●"} {s.get("key_label","Key")}</span>'
      for s in stats
  )}
</div>
""",
        unsafe_allow_html=True,
    )


def _render_summary_stats(stats: list[dict], calls: list[dict]) -> None:
    total_calls_all = sum(s.get("total_calls", 0) for s in stats)
    total_tokens = sum(s.get("total_tokens", 0) for s in stats)
    total_prompt = sum(s.get("total_prompt_tokens", 0) for s in stats)
    total_resp = sum(s.get("total_response_tokens", 0) for s in stats)
    total_cost = _cost_usd(total_prompt, total_resp)
    healthy = sum(1 for s in stats if s.get("status") == "healthy")
    total_keys = len(stats)

    # Also count from actual call records if available
    if calls:
        api_total_calls = len(calls)
        api_total_tokens = sum(c.get("total_tokens", 0) for c in calls)
        api_prompt = sum(c.get("prompt_tokens", 0) for c in calls)
        api_resp = sum(c.get("response_tokens", 0) for c in calls)
        api_cost = _cost_usd(api_prompt, api_resp)
        # Use API data when available (more accurate)
        total_calls_all = max(total_calls_all, api_total_calls)
        total_tokens = max(total_tokens, api_total_tokens)
        total_cost = max(total_cost, api_cost)

    stat_row([
        {"label": "Total LLM Calls", "value": f"{total_calls_all:,}", "icon": "cpu",
         "hint_html": "Across all agents & keys"},
        {"label": "Total Tokens Used", "value": f"{total_tokens:,}", "icon": "hash",
         "hint_html": f"Prompt + response tokens"},
        {"label": "Estimated Cost", "value": f"${total_cost:.4f}", "icon": "trending-up",
         "tone": "green" if total_cost < 0.5 else "orange",
         "hint_html": "USD · Gemini Flash pricing"},
        {"label": "Active Keys", "value": f"{healthy}/{total_keys}", "icon": "key",
         "tone": "green" if healthy == total_keys else ("orange" if healthy > 0 else "red"),
         "hint_html": f"{total_keys - healthy} in cooldown or failed"},
    ])


def _render_agent_breakdown(calls: list[dict]) -> None:
    section("Per-Agent Breakdown", "Token consumption by agent across all reviewed applications.")
    if not calls:
        empty_state("No call records yet", "Records appear after the first review is completed.")
        return

    agent_stats: dict[str, dict] = {}
    for c in calls:
        name = c.get("agent_name", "unknown")
        if name not in agent_stats:
            agent_stats[name] = {"calls": 0, "prompt_tokens": 0, "response_tokens": 0, "total_tokens": 0,
                                  "total_latency_ms": 0}
        agent_stats[name]["calls"] += 1
        agent_stats[name]["prompt_tokens"] += c.get("prompt_tokens", 0)
        agent_stats[name]["response_tokens"] += c.get("response_tokens", 0)
        agent_stats[name]["total_tokens"] += c.get("total_tokens", 0)
        agent_stats[name]["total_latency_ms"] += c.get("latency_milliseconds", 0)

    rows = []
    for agent_name, s in sorted(agent_stats.items(), key=lambda x: -x[1]["total_tokens"]):
        display_name = agent_name.replace("_agent", "").replace("_", " ").title()
        avg_latency = s["total_latency_ms"] / max(s["calls"], 1) / 1000
        est_cost = _cost_usd(s["prompt_tokens"], s["response_tokens"])
        rows.append({
            "Agent": display_name,
            "Calls": s["calls"],
            "Prompt Tokens": s["prompt_tokens"],
            "Response Tokens": s["response_tokens"],
            "Total Tokens": s["total_tokens"],
            "Avg Latency (s)": round(avg_latency, 2),
            "Est. Cost (USD)": f"${est_cost:.4f}",
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Total Tokens": st.column_config.ProgressColumn(
                format="%d",
                min_value=0,
                max_value=max(r["Total Tokens"] for r in rows) if rows else 1,
            ),
            "Calls": st.column_config.NumberColumn(width="small"),
        },
    )

    # Bar chart of total tokens per agent
    chart_data = pd.DataFrame({
        "Agent": [r["Agent"] for r in rows],
        "Total Tokens": [r["Total Tokens"] for r in rows],
    }).set_index("Agent")
    st.bar_chart(chart_data, color="#00C896", height=240)


def _render_tokens_over_time(calls: list[dict]) -> None:
    section("Token Usage Over Time", "Total tokens per model call, in call order.")
    if not calls:
        empty_state("No data yet", "Token history appears after the first LLM call.")
        return

    df = pd.DataFrame([{
        "Call #": i + 1,
        "Agent": c.get("agent_name", "?").replace("_agent", "").replace("_", " ").title(),
        "Total Tokens": c.get("total_tokens", 0),
        "Latency (s)": round(c.get("latency_milliseconds", 0) / 1000, 2),
    } for i, c in enumerate(calls)])

    col_tokens, col_latency = st.columns(2)
    with col_tokens:
        st.markdown("**Tokens per call**")
        st.line_chart(df.set_index("Call #")[["Total Tokens"]], color=["#00C896"], height=200)
    with col_latency:
        st.markdown("**Latency per call (seconds)**")
        st.line_chart(df.set_index("Call #")[["Latency (s)"]], color=["#60a5fa"], height=200)


def _render_pricing_note() -> None:
    st.markdown(
        f"""
<div style="padding:12px 16px;background:var(--pw-subtle);border:1px solid var(--pw-line);
border-radius:10px;font-size:13px;color:var(--pw-muted);margin-top:8px">
  <strong style="color:var(--pw-ink)">Cost formula:</strong>
  &nbsp;Prompt tokens × <code>${config.GEMINI_INPUT_COST_PER_MILLION}/1M</code>
  + Response tokens × <code>${config.GEMINI_OUTPUT_COST_PER_MILLION}/1M</code>
  &nbsp;·&nbsp; Gemini Flash pricing · Estimates only
</div>
""",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

def render_llm_cost_page() -> None:
    """LLM Cost & API Health dashboard."""
    page_header(
        config.PAGE_COST,
        "Real-time API key health, token consumption, and cost estimates across all Gemini calls.",
    )

    col_refresh, col_info = st.columns([1, 5])
    with col_refresh:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    with col_info:
        st.caption("Data updates on every page load. Click Refresh to see the latest figures.")

    spacer(8)

    # Load data
    with st.spinner("Loading API stats…"):
        key_stats = _load_router_stats()
        llm_calls = _get_all_llm_calls()

    # Summary stats
    _render_summary_stats(key_stats, llm_calls)
    spacer(16)
    _render_pricing_note()
    spacer(20)

    # Tabs for sections
    tab_keys, tab_agents, tab_timeline = st.tabs(
        ["🔑 API Key Health", "🤖 Agent Breakdown", "📈 Usage Timeline"]
    )

    with tab_keys:
        spacer(8)
        _render_key_health(key_stats)

    with tab_agents:
        spacer(8)
        _render_agent_breakdown(llm_calls)

    with tab_timeline:
        spacer(8)
        _render_tokens_over_time(llm_calls)

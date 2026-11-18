"""Entry point 6: the dashboard's front door — the service check, signing in, and the
navigation. Run it through Streamlit:

    python -m streamlit run run_dashboard.py
"""

import datetime

import httpx
import streamlit as st

from config import config
from dashboard.api_client import SIGNED_IN_USER_KEY, call_service
from dashboard.application_detail import render_application_detail_page
from dashboard.application_queue import PAGES_KEY, render_application_queue_page
from dashboard.audit_trail import render_audit_trail_page
from dashboard.connection_chat import render_connection_chat_page
from dashboard.decision_queue import render_decision_queue_page
from dashboard.llm_cost_dashboard import render_llm_cost_page
from dashboard.sign_in import render_sign_in_page
from dashboard.ui import escape, inject_theme

PAGE_RENDERERS = {
    config.PAGE_QUEUE: render_application_queue_page,
    config.PAGE_DETAIL: render_application_detail_page,
    config.PAGE_DECISION: render_decision_queue_page,
    config.PAGE_AUDIT: render_audit_trail_page,
    config.PAGE_CHAT: render_connection_chat_page,
    config.PAGE_COST: render_llm_cost_page,
}
PAGE_ICONS = {
    config.PAGE_QUEUE: ":material/format_list_numbered:",
    config.PAGE_DETAIL: ":material/description:",
    config.PAGE_DECISION: ":material/gavel:",
    config.PAGE_AUDIT: ":material/history:",
    config.PAGE_CHAT: ":material/forum:",
    config.PAGE_COST: ":material/monitoring:",
}
PAGE_URL_PATHS = {
    config.PAGE_QUEUE: "queue",
    config.PAGE_DETAIL: "application",
    config.PAGE_DECISION: "decisions",
    config.PAGE_AUDIT: "audit",
    config.PAGE_CHAT: "chat",
    config.PAGE_COST: "cost",
}

# Roles that can see the LLM Cost page (all roles)
PAGE_ROLE_ACCESS = {
    config.PAGE_QUEUE: [config.ROLE_CONNECTIONS_ENGINEER, config.ROLE_CONNECTIONS_COORDINATOR],
    config.PAGE_DETAIL: [config.ROLE_CONNECTIONS_ENGINEER, config.ROLE_CONNECTIONS_COORDINATOR],
    config.PAGE_DECISION: [config.ROLE_CONNECTIONS_ENGINEER],
    config.PAGE_AUDIT: [config.ROLE_CONNECTIONS_ENGINEER, config.ROLE_CONNECTIONS_COORDINATOR],
    config.PAGE_CHAT: [config.ROLE_CONNECTIONS_ENGINEER, config.ROLE_CONNECTIONS_COORDINATOR,
                       config.ROLE_CUSTOMER_SERVICE_ADVISOR],
    config.PAGE_COST: [config.ROLE_CONNECTIONS_ENGINEER, config.ROLE_CONNECTIONS_COORDINATOR,
                       config.ROLE_CUSTOMER_SERVICE_ADVISOR],
}


def _service_answers():
    try:
        response = httpx.get(f"{config.API_BASE_URL}/health", timeout=5)
        return response.json() if response.status_code == 200 else None
    except httpx.HTTPError:
        return None


def _sign_out():
    call_service("POST", "/auth/signout")
    st.session_state.clear()


def _render_sidebar_health_widget():
    """Render a compact API key health panel in the sidebar."""
    try:
        from agentic.api_key_router import get_router
        router = get_router()
        stats = router.get_all_stats()
        total = len(stats)
        healthy = sum(1 for s in stats if s["status"] == "healthy")
        cooldown = sum(1 for s in stats if s["status"] == "cooldown")
        failed = sum(1 for s in stats if s["status"] == "failed")

        status_color = "#16a34a" if failed == 0 and cooldown == 0 else (
            "#ca8a04" if failed == 0 else "#dc2626"
        )

        dots_html = ""
        for s in stats:
            color = {"healthy": "#16a34a", "cooldown": "#ca8a04", "failed": "#dc2626"}.get(
                s["status"], "#6b7280"
            )
            title = f"Key {s['key_index']}: {s['status']}"
            dots_html += (
                f'<span title="{title}" style="width:8px;height:8px;border-radius:50%;'
                f'background:{color};display:inline-block;margin:1px"></span>'
            )

        st.markdown(
            f'<div style="padding:10px 12px;border-radius:10px;background:var(--pw-subtle,#F2F3F0);'
            f'border:1px solid var(--pw-line,#E4E6E1);margin-bottom:12px">'
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'margin-bottom:6px">'
            f'<span style="font-size:12px;font-weight:600;color:var(--pw-ink,#16201D)">API Keys</span>'
            f'<span style="font-size:11px;color:{status_color};font-weight:500;display:flex;align-items:center;gap:8px;">'
            f'<span style="display:inline-flex;align-items:center;gap:4px;">🟢 {healthy}</span>'
            f'<span style="display:inline-flex;align-items:center;gap:4px;">🟡 {cooldown}</span>'
            f'<span style="display:inline-flex;align-items:center;gap:4px;">🔴 {failed}</span>'
            f'</span>'
            f'</div>'
            f'<div style="display:flex;gap:3px;flex-wrap:wrap">{dots_html}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    except Exception:
        pass  # Silently skip if router not available


def _render_sidebar_clock():
    """Show the current UTC time in the sidebar."""
    now = datetime.datetime.now(datetime.timezone.utc)
    st.markdown(
        f'<div style="font-size:11px;color:var(--pw-muted,#6A7471);text-align:center;'
        f'padding:4px 0 8px">{now.strftime("%H:%M UTC · %d %b %Y")}</div>',
        unsafe_allow_html=True,
    )


def main():
    """One screen to work from, with only the pages the signed-in person's role is offered."""
    st.set_page_config(
        page_title=config.DASHBOARD_TITLE,
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(config.DASHBOARD_PAGE_STYLE, unsafe_allow_html=True)
    inject_theme()

    health = _service_answers()
    if not health:
        st.error(
            f"The PhaseWise AI service is not answering at {config.API_BASE_URL}. Start it from "
            f"the Project folder with: python run_api_service.py",
            icon=":material/cloud_off:",
        )
        return
    st.session_state["service_health"] = health

    user = st.session_state.get(SIGNED_IN_USER_KEY)
    if user is None:
        st.navigation(
            [st.Page(render_sign_in_page, title="Sign in", icon=":material/login:",
                     url_path="signin", default=True)],
            position="hidden",
        ).run()
        return

    # Build pages for this user's role — including cost page for all roles
    user_role = user["role"]
    allowed_pages = [
        name for name in PAGE_RENDERERS
        if user_role in PAGE_ROLE_ACCESS.get(name, [])
    ]
    # Also respect original page access from user["pages"] for core pages
    core_pages = user.get("pages", [])
    for page in core_pages:
        if page not in allowed_pages and page != config.PAGE_COST:
            allowed_pages.append(page)

    pages = {
        name: st.Page(
            PAGE_RENDERERS[name],
            title=name,
            icon=PAGE_ICONS[name],
            url_path=PAGE_URL_PATHS[name],
            default=(position == 0),
        )
        for position, name in enumerate(allowed_pages)
        if name in PAGE_RENDERERS
    }
    st.session_state[PAGES_KEY] = pages
    navigation = st.navigation(list(pages.values()))

    with st.sidebar:
        # Brand header
        mode_label = "Gemini live" if health.get("llm_mode") == "gemini" else "Offline demo"
        mode_colour = "#16a34a" if health.get("llm_mode") == "gemini" else "#ca8a04"
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:11px;padding:4px 2px 16px">'
            f'<div style="width:36px;height:36px;border-radius:10px;background:var(--pw-brand,#0B6B57);'
            f'display:flex;align-items:center;justify-content:center;color:#fff;font-size:20px;'
            f'flex-shrink:0;box-shadow:0 0 0 2px rgba(11,107,87,0.25)">⚡</div>'
            f'<div>'
            f'<div style="font-size:15px;font-weight:800;letter-spacing:-0.025em;'
            f'color:var(--pw-ink,#16201D)">{escape(config.DASHBOARD_TITLE)}</div>'
            f'<div style="font-size:11px;color:var(--pw-muted,#6A7471);margin-top:1px">'
            f'{escape(config.ORGANISATION_NAME)}</div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        # User card
        role_colours = {
            config.ROLE_CONNECTIONS_ENGINEER: ("#0B6B57", "#E9F2EE"),
            config.ROLE_CONNECTIONS_COORDINATOR: ("#1F4E8C", "#EDF3FB"),
            config.ROLE_CUSTOMER_SERVICE_ADVISOR: ("#5934A0", "#F3EFFA"),
        }
        rc, rbg = role_colours.get(user_role, ("#4A5451", "#F3F4F2"))
        st.markdown(
            f'<div style="padding:11px 13px;border-radius:11px;background:var(--pw-subtle,#F2F3F0);'
            f'border:1px solid var(--pw-line,#E4E6E1);margin-bottom:12px">'
            f'<div style="font-weight:700;font-size:14px;color:var(--pw-ink,#16201D)">'
            f'{escape(user["display_name"])}</div>'
            f'<div style="margin-top:5px">'
            f'<span style="display:inline-flex;align-items:center;padding:2px 9px;border-radius:20px;'
            f'background:{rbg};color:{rc};font-size:11.5px;font-weight:600">'
            f'{escape(user_role)}</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # LLM mode status
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:7px;font-size:12px;'
            f'color:var(--pw-muted,#6A7471);padding:4px 2px 10px">'
            f'<span style="width:7px;height:7px;border-radius:50%;background:{mode_colour};'
            f'display:inline-block;flex-shrink:0"></span>'
            f'{mode_label} · <span style="opacity:.7;overflow:hidden;text-overflow:ellipsis;'
            f'white-space:nowrap;max-width:110px">{escape(health.get("model", ""))}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # API key health widget
        _render_sidebar_health_widget()

        st.write("")

        if st.button("Sign out", icon=":material/logout:", use_container_width=True):
            _sign_out()
            st.rerun()

        _render_sidebar_clock()

    navigation.run()


if __name__ == "__main__":
    main()

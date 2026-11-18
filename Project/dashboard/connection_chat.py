"""The connection chat page — rich Markdown responses, typing indicator, suggestions."""

import streamlit as st

from config import config
from dashboard.api_client import call_service
from dashboard.ui import badge_html, callout, chat_type_colour, escape, page_header, section

SUGGESTIONS = [
    "What does the heat pump standard require?",
    "What does the reviewer check in an earthing statement?",
    "When does a looped service mean the network is assessed first?",
    "What documentation must an EV charge point installer provide?",
    "What is the power factor requirement for solar PV?",
]
PENDING_KEY = "chat_pending"

# CSS for rich chat bubbles
_CHAT_CSS = """
<style>
/* ---- Chat container ---- */
.pw-chat-turn { margin-bottom: 18px; }

/* ---- User bubble ---- */
.pw-chat-user {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    align-items: flex-end;
    margin: 8px 0;
}
.pw-chat-user-bubble {
    background: var(--pw-brand, #0B6B57);
    color: #fff;
    border-radius: 18px 18px 4px 18px;
    padding: 11px 16px;
    max-width: 72%;
    font-size: 14px;
    line-height: 1.55;
    box-shadow: 0 2px 8px rgba(0,200,150,0.18);
}

/* ---- Assistant bubble ---- */
.pw-chat-assistant {
    display: flex;
    gap: 12px;
    align-items: flex-start;
    margin: 8px 0;
}
.pw-chat-avatar {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: var(--pw-brand, #0B6B57);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    color: #fff;
    font-size: 18px;
}
.pw-chat-assistant-bubble {
    background: var(--pw-surface, #fff);
    border: 1px solid var(--pw-line, #E4E6E1);
    border-radius: 4px 18px 18px 18px;
    padding: 14px 18px;
    max-width: 76%;
    font-size: 14px;
    line-height: 1.65;
    box-shadow: var(--pw-shadow, 0 1px 4px rgba(0,0,0,0.06));
}
.pw-chat-assistant-bubble p { margin: 0 0 8px; color: var(--pw-ink, #16201D); }
.pw-chat-assistant-bubble p:last-child { margin-bottom: 0; }
.pw-chat-assistant-bubble ul, .pw-chat-assistant-bubble ol {
    margin: 6px 0 8px 18px; padding: 0;
}
.pw-chat-assistant-bubble li { margin-bottom: 3px; color: var(--pw-ink-2, #3A4643); }
.pw-chat-assistant-bubble strong { color: var(--pw-ink, #16201D); font-weight: 600; }
.pw-chat-assistant-bubble code {
    font-family: var(--pw-font-mono, monospace);
    font-size: 12.5px;
    background: var(--pw-subtle, #F2F3F0);
    border-radius: 4px;
    padding: 1px 5px;
    color: var(--pw-brand, #0B6B57);
}
.pw-chat-assistant-bubble h3 { font-size: 14px; font-weight: 600; margin: 10px 0 4px; color: var(--pw-ink, #16201D); }

.pw-chat-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 8px;
    flex-wrap: wrap;
}
.pw-chat-source {
    color: var(--pw-muted, #6A7471);
    font-size: 12px;
    display: flex;
    align-items: center;
    gap: 4px;
}

/* ---- Suggestion chips ---- */
.pw-suggestions {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin: 16px 0;
}
.pw-suggestion-chip {
    background: var(--pw-surface, #fff);
    border: 1px solid var(--pw-line, #E4E6E1);
    border-radius: 20px;
    padding: 8px 16px;
    font-size: 13.5px;
    color: var(--pw-ink-2, #3A4643);
    cursor: pointer;
    transition: all 0.18s ease;
    white-space: nowrap;
}
.pw-suggestion-chip:hover {
    border-color: var(--pw-brand, #0B6B57);
    color: var(--pw-brand, #0B6B57);
    background: var(--pw-brand-subtle, #E9F2EE);
    transform: translateY(-1px);
}

/* ---- Typing indicator ---- */
.pw-typing {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 12px 16px;
    background: var(--pw-surface, #fff);
    border: 1px solid var(--pw-line, #E4E6E1);
    border-radius: 4px 18px 18px 18px;
    width: fit-content;
}
.pw-dot {
    width: 7px; height: 7px;
    border-radius: 50%;
    background: var(--pw-brand, #0B6B57);
    animation: pw-bounce 1.2s infinite ease-in-out;
}
.pw-dot:nth-child(2) { animation-delay: 0.2s; }
.pw-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes pw-bounce {
    0%, 80%, 100% { transform: scale(0.7); opacity: 0.5; }
    40% { transform: scale(1); opacity: 1; }
}
</style>
"""

_MARKDOWN_JS = """
<script>
// Enhance markdown rendering in chat bubbles
document.querySelectorAll('.pw-chat-answer-text').forEach(el => {
    const text = el.textContent;
    // Convert **bold** to <strong>
    el.innerHTML = el.innerHTML
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>');
});
</script>
"""


def _unique_turns(turns):
    """Keep one visible copy when a chat exchange has been recorded twice."""
    seen = set()
    unique = []
    for turn in turns:
        key = (turn["question_text"], turn["question_type"], turn["answer_text"],
               turn["source_documents"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(turn)
    return unique


def _format_answer(answer_text: str) -> str:
    """Format raw answer text as rich markdown-aware HTML."""
    import html
    # Escape first
    text = answer_text.strip()

    # Convert markdown-like patterns to HTML
    import re
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # Inline code
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    # Headers (## heading)
    text = re.sub(r'^#{2,3}\s+(.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)

    # Bullet lists: lines starting with - or *
    lines = text.split('\n')
    result_lines = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        if re.match(r'^[-•*]\s+', stripped):
            if not in_list:
                result_lines.append('<ul>')
                in_list = True
            item_text = re.sub(r'^[-•*]\s+', '', stripped)
            result_lines.append(f'<li>{item_text}</li>')
        else:
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            if stripped:
                result_lines.append(f'<p>{stripped}</p>')
            else:
                result_lines.append('')
    if in_list:
        result_lines.append('</ul>')
    return '\n'.join(result_lines)


def _render_turn(turn):
    """Render one conversation turn with rich formatting."""
    # User message
    st.markdown(
        f'<div class="pw-chat-user">'
        f'<div class="pw-chat-user-bubble">{escape(turn["question_text"])}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Assistant response
    formatted_answer = _format_answer(turn["answer_text"])
    type_badge = badge_html(turn["question_type"], chat_type_colour(turn["question_type"]))

    source_html = ""
    if turn["source_documents"]:
        source_html = (
            f'<div class="pw-chat-source">'
            f'<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            f'<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/>'
            f'<path d="M14 2v4a2 2 0 0 0 2 2h4"/></svg>'
            f'Sources: {escape(turn["source_documents"])}</div>'
        )

    st.markdown(
        f'<div class="pw-chat-assistant">'
        f'<div class="pw-chat-avatar">⚡</div>'
        f'<div class="pw-chat-assistant-bubble">'
        f'<div class="pw-chat-meta">{type_badge}</div>'
        f'<div style="margin-top:10px">{formatted_answer}</div>'
        f'{source_html}'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_connection_chat_page():
    """Let anyone signed in ask the connection assistant a question in a fresh thread."""
    st.markdown(_CHAT_CSS, unsafe_allow_html=True)

    if "pw_chat_session_turns" not in st.session_state:
        st.session_state["pw_chat_session_turns"] = []

    if st.sidebar.button("New conversation", use_container_width=True, type="secondary"):
        st.session_state["pw_chat_session_turns"] = []
        st.session_state.pop(PENDING_KEY, None)
        st.rerun()

    page_header(
        config.PAGE_CHAT,
        "Answers come from Merrowdale's documents and records only. "
        "Advisors never receive a prediction.",
    )

    health = st.session_state.get("service_health", {})
    model_label = health.get("model", "configured model")
    mode_label = "live Gemini" if health.get("llm_mode") == "gemini" else "offline demo"

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;'
        f'padding:9px 14px;background:var(--pw-surface);border:1px solid var(--pw-line);'
        f'border-radius:10px;font-size:13px;color:var(--pw-muted)">'
        f'<span style="width:8px;height:8px;border-radius:50%;background:'
        f'{"#16a34a" if health.get("llm_mode") == "gemini" else "#ca8a04"};'
        f'display:inline-block;flex-shrink:0"></span>'
        f'Using <strong style="color:var(--pw-ink)">{model_label}</strong> · {mode_label} · '
        f'Sources shown below each answer'
        f'</div>',
        unsafe_allow_html=True,
    )

    for turn in st.session_state["pw_chat_session_turns"]:
        _render_turn(turn)

    if not st.session_state["pw_chat_session_turns"]:
        section("Start with a question", "A few things people often ask.")
        cols = st.columns(len(SUGGESTIONS[:3]))
        for col, suggestion in zip(cols, SUGGESTIONS[:3]):
            if col.button(suggestion, use_container_width=True, icon=":material/arrow_outward:"):
                st.session_state[PENDING_KEY] = suggestion
        st.markdown("")
        cols2 = st.columns(len(SUGGESTIONS[3:]))
        for col, suggestion in zip(cols2, SUGGESTIONS[3:]):
            if col.button(suggestion, use_container_width=True, icon=":material/arrow_outward:"):
                st.session_state[PENDING_KEY] = suggestion

    question = st.chat_input(
        "Ask about a standard, a rule, a statement guide or an application",
        max_chars=config.CHAT_QUESTION_MAXIMUM_CHARACTERS,
    )
    question = question or st.session_state.pop(PENDING_KEY, None)
    if question is None:
        return
    if len(question.strip()) < config.CHAT_QUESTION_MINIMUM_CHARACTERS:
        callout(
            f"Ask a question of at least {config.CHAT_QUESTION_MINIMUM_CHARACTERS} characters.",
            tone="warning",
        )
        return

    st.markdown(
        '<div class="pw-chat-assistant" style="margin:8px 0">'
        '<div class="pw-chat-avatar">⚡</div>'
        '<div class="pw-typing"><div class="pw-dot"></div>'
        '<div class="pw-dot"></div><div class="pw-dot"></div></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    result = call_service(
        "POST", "/chat/ask",
        payload={"question": question.strip()},
        waiting_message="Reading the documents",
    )
    if isinstance(result, dict):
        st.session_state["pw_chat_session_turns"].append({
            "question_text": question.strip(),
            "answer_text": result.get("answer", ""),
            "question_type": result.get("question_type", "CHAT"),
            "source_documents": ", ".join(result.get("source_documents", [])),
        })
    st.rerun()

"""Recalls the last few exchanges of one person's own conversation."""

from config import config
from persistence.models import ChatTurn
from persistence.repository import fetch_chat_turns


def recall_conversation(session, username, question_text):
    """Start a fresh conversation by default; do not carry older chat context forward."""
    return {
        "history_text": config.CHAT_FIRST_QUESTION_TEXT,
        "search_text": question_text.strip(),
        "previous_question": "",
    }

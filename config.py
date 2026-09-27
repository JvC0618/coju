"""Configuration; runtime choices are local to each Streamlit execution context."""
from contextvars import ContextVar
import os

_runtime_key = ContextVar("coju_runtime_key", default="")
_demo_mode = ContextVar("coju_demo_mode", default=None)


def _secret(key, default=""):
    if os.environ.get(key):
        return os.environ[key]
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default


LLM_API_KEY = _secret("LLM_API_KEY")
LLM_BASE_URL = _secret("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = _secret("LLM_MODEL", "gpt-4o-mini")
FORCE_OFFLINE = _secret("COJU_OFFLINE", "0") == "1"


def set_runtime_key(key):
    _runtime_key.set((key or "").strip())


def set_demo_mode(value):
    _demo_mode.set(value)


def get_amap_key():
    return _runtime_key.get() or _secret("AMAP_KEY")


def offline_mode():
    selected = _demo_mode.get()
    return FORCE_OFFLINE or (selected if selected is not None else not bool(get_amap_key()))


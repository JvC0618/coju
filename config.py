"""
CoJu 配置 —— API Key 管理。
Key 来源优先级:
  1. 运行时用户输入 (set_runtime_key, 界面里每个用户自己填) ← 最高
  2. 环境变量 / Streamlit Secrets
  3. 留空 → OFFLINE 离线演示模式
"""
import os

# 运行时覆盖 (用户在界面输入的 key, 存这里)
_RUNTIME_KEY = ""


def _secret(key, default=""):
    if os.environ.get(key):
        return os.environ[key]
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return default


# 默认 key (本地测试用; 部署版留空)
_DEFAULT_AMAP_KEY = _secret("AMAP_KEY", "")

LLM_API_KEY = _secret("LLM_API_KEY", "")
LLM_BASE_URL = _secret("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = _secret("LLM_MODEL", "gpt-4o-mini")

FORCE_OFFLINE = _secret("COJU_OFFLINE", "0") == "1"


def set_runtime_key(key):
    """界面里用户填入自己的 key 时调用, 运行时覆盖。"""
    global _RUNTIME_KEY
    _RUNTIME_KEY = (key or "").strip()


def get_amap_key():
    """当前生效的 key: 优先用户运行时输入, 否则默认/环境。"""
    return _RUNTIME_KEY or _DEFAULT_AMAP_KEY


def offline_mode():
    """无有效 key 或强制离线 → 走离线数据。"""
    return FORCE_OFFLINE or not get_amap_key()

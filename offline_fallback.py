"""
offline_fallback.py — 後方互換 re-export

分割後の fallback パッケージへの薄いラッパー。
既存の import 文 (from offline_fallback import fallback_action, is_ollama_error_action)
を変更せずに動作させる。
"""

from fallback import fallback_action  # noqa: F401
from fallback import is_ollama_error_text, is_ollama_error_action  # noqa: F401

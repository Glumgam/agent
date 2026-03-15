"""
tool_result.py — 統一ツール戻り値型
"""

from dataclasses import dataclass, field


@dataclass
class ToolResult:
    ok: bool          # 成功/失敗
    output: str       # LLMに渡す観察文字列
    data: dict = field(default=None)  # オプション: 構造化データ

    def __str__(self):
        return self.output

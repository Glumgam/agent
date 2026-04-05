"""
prompt_improver.py — 自己改善ループ（Self-reflection / Iterative refinement）
失敗の原因を分析し、プロンプトを自動改善する。

設計思想:
  「失敗したら再試行」ではなく「失敗したら原因を特定してプロンプトを改善する」
  失敗パターンを prompt_rules.json に蓄積し、次回生成時に先行注入する。
"""
import json
import re
from pathlib import Path
from datetime import datetime

RULES_FILE = Path(__file__).parent / "prompt_rules.json"

DEFAULT_RULES: dict = {
    "language_fix": "出力は必ず日本語のみ。英語は一切使わない。",
    "title_fix": "1行目は必ず「# 」で始まるMarkdownタイトル行にする。",
    "length_fix": "2500文字以上書くこと。途中で止まらないこと。",
    "failures": {},          # {key: {count, fix, last_seen}}
    "success_patterns": [],  # 将来利用
}


# ---------------------------------------------------------------------------
# ルール永続化
# ---------------------------------------------------------------------------

def load_rules() -> dict:
    if RULES_FILE.exists():
        try:
            return json.loads(RULES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    rules = DEFAULT_RULES.copy()
    rules["failures"] = {}
    rules["success_patterns"] = []
    return rules


def save_rules(rules: dict) -> None:
    RULES_FILE.write_text(
        json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# 原因分析（因果チェーン）
# ---------------------------------------------------------------------------

def analyze_failure(content: str, issues: list) -> dict:
    """
    失敗の原因を分析して仮説と修正案を返す。

    Returns:
        {"cause": str, "hypothesis": str, "fix": str}
    """
    issues_str = " ".join(str(i) for i in issues)
    english_ratio = len(re.findall(r'[a-zA-Z]', content)) / max(len(content), 1)

    if english_ratio > 0.3 or len(content) < 100:
        return {
            "cause": f"英語出力比率が高い ({english_ratio:.1%}) またはコンテンツが空 ({len(content)}文字)",
            "hypothesis": "モデルが英語で思考しそのまま出力している",
            "fix": "日本語で記事本文のみを出力してください。思考過程は不要です。最初の1行は「# 」から始めてください。",
        }

    if "タイトル行なし" in issues_str or "タイトル" in issues_str:
        return {
            "cause": "タイトル行が正しい形式でない",
            "hypothesis": "プロンプトのタイトル指示が不明確またはモデルが無視した",
            "fix": "必ず最初の行を「# 記事タイトル」の形式（半角シャープ＋スペース）で開始してください。",
        }

    if "極端に少ない" in issues_str or "内容が少ない" in issues_str or ("文字" in issues_str and len(content) < 1500):
        return {
            "cause": f"文字数不足 ({len(content)}文字)",
            "hypothesis": "max_tokensが少ないまたはモデルが途中で出力を止めた",
            "fix": "各セクションを最低300文字以上書いてください。途中で止まらず最後まで書いてください。",
        }

    if "必須セクションなし" in issues_str or "市場概況" in issues_str:
        return {
            "cause": "必須セクション（市場概況・まとめ）が欠如",
            "hypothesis": "テンプレートの構成指示がモデルに伝わっていない",
            "fix": "「## 本日の市場概況」「## まとめ」「## 免責事項」を必ず含めてください。",
        }

    if "免責事項" in issues_str:
        return {
            "cause": "免責事項セクションが欠如",
            "hypothesis": "記事末尾の免責事項をモデルが省略した",
            "fix": "記事の最後に「## 免責事項\n\n※本記事は情報提供を目的としており...」を追加してください。",
        }

    if "中国語" in issues_str:
        return {
            "cause": "中国語文字が混入している",
            "hypothesis": "モデルの訓練データに中国語が含まれており混入した",
            "fix": "中国語（简体字・繁体字）は絶対に使わないこと。日本語のみで書いてください。",
        }

    return {
        "cause": "不明 / 複合的な問題",
        "hypothesis": "プロンプトの指示が競合している可能性",
        "fix": "",
    }


# ---------------------------------------------------------------------------
# プロンプト修正
# ---------------------------------------------------------------------------

def apply_fix(prompt: str, fix: str) -> str:
    """分析結果をプロンプト末尾に注入する。"""
    if not fix:
        return prompt
    return prompt + f"\n\n【自己改善追加指示】\n{fix}"


def get_prompt_prefix(rules: dict) -> str:
    """
    学習済みルールと高頻度失敗パターン (count > 2) から
    プロンプト先行注入テキストを生成する。
    """
    parts: list[str] = []
    for key in ("language_fix", "title_fix", "length_fix"):
        val = rules.get(key, "")
        if val:
            parts.append(f"- {val}")

    existing = "\n".join(parts)
    for _key, meta in rules.get("failures", {}).items():
        if isinstance(meta, dict) and meta.get("count", 0) > 2:
            fix = meta.get("fix", "")
            if fix and fix not in existing:
                parts.append(f"- {fix}")
                existing += fix

    if not parts:
        return ""
    return "【生成ルール】\n" + "\n".join(parts)


# ---------------------------------------------------------------------------
# 記録
# ---------------------------------------------------------------------------

def record_failure(rules: dict, issue: str, fix: str) -> None:
    key = re.sub(r'\s+', '_', issue.strip())[:60]
    entry = rules.setdefault("failures", {}).setdefault(
        key, {"count": 0, "fix": fix, "last_seen": ""}
    )
    entry["count"] += 1
    entry["fix"] = fix
    entry["last_seen"] = datetime.now().isoformat()


def record_success(rules: dict, prompt: str, content: str) -> None:
    patterns = rules.setdefault("success_patterns", [])
    patterns.append({
        "prompt_head": prompt[:200],
        "content_length": len(content),
        "recorded_at": datetime.now().isoformat(),
    })
    rules["success_patterns"] = patterns[-50:]


# ---------------------------------------------------------------------------
# SelfImprovingGenerator
# ---------------------------------------------------------------------------

class SelfImprovingGenerator:
    """
    自己改善ループを持つ記事生成器。

    失敗 → 原因分析 → 仮説 → プロンプト修正 → 再試行 → 評価 → ルール更新

    Usage:
        gen = SelfImprovingGenerator(max_attempts=3)
        content, meta = gen.generate(
            prompt_fn=lambda p: ask_finance_llmjp4(p),
            review_fn=lambda c: review_article(c, use_llmjp4=True),
            base_prompt=hatena_prompt,
        )
    """

    def __init__(self, max_attempts: int = 3):
        self.max_attempts = max_attempts
        self.rules = load_rules()

    def build_initial_prompt(self, base_prompt: str) -> str:
        prefix = get_prompt_prefix(self.rules)
        return (prefix + "\n\n" + base_prompt) if prefix else base_prompt

    def generate(self, prompt_fn, review_fn, base_prompt: str) -> tuple:
        """
        Returns:
            (best_content: str, metadata: dict)
        """
        current_prompt = self.build_initial_prompt(base_prompt)
        history: list[dict] = []
        best_content = ""
        best_score = -1

        for attempt in range(self.max_attempts):
            print(f"  🔄 自己改善 試行 {attempt + 1}/{self.max_attempts}")

            content = prompt_fn(current_prompt) or ""

            try:
                quality = review_fn(content)
            except Exception as e:
                print(f"  ⚠️ レビューエラー: {e}")
                quality = {"score": 0, "issues": [str(e)], "passed": False}

            issues = quality.get("issues", [])
            score  = quality.get("score", 0)
            passed = quality.get("passed", False)

            history.append({
                "attempt": attempt + 1,
                "content_length": len(content),
                "score": score,
                "issues": issues,
            })

            print(
                f"  📊 試行{attempt + 1}: {len(content)}文字 "
                f"score={score}/10 {'✅' if passed else '❌'} "
                f"問題={issues[:2]}"
            )

            if score > best_score or (score == best_score and len(content) > len(best_content)):
                best_score   = score
                best_content = content

            if passed and len(content) > 1500:
                record_success(self.rules, current_prompt, content)
                save_rules(self.rules)
                print(f"  ✅ 自己改善ループ: {attempt + 1}回で成功")
                return content, {"attempts": attempt + 1, "history": history,
                                 "best_attempt": attempt + 1}

            if attempt >= self.max_attempts - 1:
                break

            analysis = analyze_failure(content, issues)
            print(f"  🔍 原因: {analysis['cause']}")
            print(f"  💡 仮説: {analysis['hypothesis']}")

            if analysis["fix"]:
                for issue in issues:
                    record_failure(self.rules, str(issue), analysis["fix"])
                save_rules(self.rules)
                current_prompt = apply_fix(current_prompt, analysis["fix"])
                print(f"  🔧 プロンプト修正: {analysis['fix'][:60]}...")

        best_num = max(history, key=lambda x: (x["score"], x["content_length"]))["attempt"]
        print(f"  ⚠️ 最大試行数到達 → 試行{best_num}の結果(score={best_score})を使用")
        return best_content, {"attempts": self.max_attempts, "history": history,
                               "best_attempt": best_num}

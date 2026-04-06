"""
prompt_improver.py — 自己改善ループ（Self-reflection / Iterative refinement）
失敗の原因を分析し、プロンプトを自動改善する。

設計思想:
  「失敗したら再試行」ではなく「失敗したら原因を特定してプロンプトを改善する」
  失敗パターンを prompt_rules.json に蓄積し、次回生成時に先行注入する。

  v2: カテゴリ分離・成功パターン活用・剪定（MAX_ACTIVE_RULES）
"""
import json
import re
from pathlib import Path
from datetime import datetime

RULES_FILE = Path(__file__).parent / "prompt_rules.json"
MAX_ACTIVE_RULES = 8   # failures テーブルの上限（剪定後）

# デフォルトのカテゴリ別ルール
DEFAULT_CATEGORIES = {
    "language":  {"fix": "出力は日本語のみ。最初の1文を日本語で書き始めること。英語・中国語は使わない。", "count": 0},
    "title":     {"fix": "1行目は必ず「# 」で始まるMarkdownタイトル行にすること。", "count": 0},
    "length":    {"fix": "2500文字以上書くこと。各セクション300文字以上。途中で止まらない。", "count": 0},
    "structure": {"fix": "## 市場概況・## まとめ・## 免責事項 の見出しを必ず含めること。", "count": 0},
}

DEFAULT_RULES: dict = {
    "categories": DEFAULT_CATEGORIES,
    "failures": {},          # {key: {count, fix, last_seen, category}}
    "success_patterns": [],  # [{score, features, timestamp}]
    # ---- v1 互換キー（移行後は使わない）----
    "language_fix": "",
    "title_fix": "",
    "length_fix": "",
}


# ---------------------------------------------------------------------------
# ルール永続化・移行
# ---------------------------------------------------------------------------

def _migrate_v1_to_v2(rules: dict) -> dict:
    """v1フォーマット（language_fix等のフラットキー）をv2に移行する。"""
    if "categories" not in rules:
        rules["categories"] = {k: dict(v) for k, v in DEFAULT_CATEGORIES.items()}
    for cat in DEFAULT_CATEGORIES:
        rules["categories"].setdefault(cat, dict(DEFAULT_CATEGORIES[cat]))
    rules.setdefault("success_patterns", [])
    rules.setdefault("failures", {})
    return rules


def load_rules() -> dict:
    if RULES_FILE.exists():
        try:
            data = json.loads(RULES_FILE.read_text(encoding="utf-8"))
            return _migrate_v1_to_v2(data)
        except Exception:
            pass
    rules = {
        "categories": {k: dict(v) for k, v in DEFAULT_CATEGORIES.items()},
        "failures": {},
        "success_patterns": [],
    }
    return rules


def save_rules(rules: dict) -> None:
    RULES_FILE.write_text(
        json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# 剪定: 古く・頻度の低いルールをカットして MAX_ACTIVE_RULES 以内に収める
# ---------------------------------------------------------------------------

def _recency_weight(last_seen: str) -> float:
    """last_seen から経過日数に基づく重みを計算（30日で 0.1 まで減衰）。"""
    try:
        days = (datetime.now() - datetime.fromisoformat(last_seen)).days
        return max(0.1, 1.0 - days / 30.0)
    except Exception:
        return 0.5


def prune_rules(rules: dict) -> dict:
    """
    count × recency_weight でスコアリングし、上位 MAX_ACTIVE_RULES 件のみ残す。
    カテゴリルールは剪定しない（失敗テーブルのみ対象）。
    """
    failures = rules.get("failures", {})
    if len(failures) <= MAX_ACTIVE_RULES:
        return rules
    scored = sorted(
        failures.items(),
        key=lambda kv: kv[1].get("count", 0) * _recency_weight(kv[1].get("last_seen", "")),
        reverse=True,
    )
    rules["failures"] = dict(scored[:MAX_ACTIVE_RULES])
    return rules


# ---------------------------------------------------------------------------
# 原因分析（因果チェーン）—— category フィールドを返す
# ---------------------------------------------------------------------------

def analyze_failure(content: str, issues: list) -> dict:
    """
    失敗の原因を分析して仮説と修正案を返す。

    Returns:
        {"category": str, "cause": str, "hypothesis": str, "fix": str}
    """
    issues_str = " ".join(str(i) for i in issues)
    english_ratio = len(re.findall(r'[a-zA-Z]', content)) / max(len(content), 1)

    if english_ratio > 0.3 or len(content) < 100:
        return {
            "category": "language",
            "cause": f"英語出力比率が高い ({english_ratio:.1%}) またはコンテンツが空 ({len(content)}文字)",
            "hypothesis": "モデルが英語で思考しそのまま出力している",
            "fix": "日本語で記事本文のみを出力してください。思考過程は不要です。最初の1行は「# 」から始めてください。",
        }

    if "タイトル行なし" in issues_str or "タイトル" in issues_str:
        return {
            "category": "title",
            "cause": "タイトル行が正しい形式でない",
            "hypothesis": "プロンプトのタイトル指示が不明確またはモデルが無視した",
            "fix": "必ず最初の行を「# 記事タイトル」の形式（半角シャープ＋スペース）で開始してください。",
        }

    if "極端に少ない" in issues_str or "内容が少ない" in issues_str or (
        "文字" in issues_str and len(content) < 1500
    ):
        return {
            "category": "length",
            "cause": f"文字数不足 ({len(content)}文字)",
            "hypothesis": "max_tokensが少ないまたはモデルが途中で出力を止めた",
            "fix": "各セクションを最低300文字以上書いてください。途中で止まらず最後まで書いてください。",
        }

    if "必須セクションなし" in issues_str or "市場概況" in issues_str:
        return {
            "category": "structure",
            "cause": "必須セクション（市場概況・まとめ）が欠如",
            "hypothesis": "テンプレートの構成指示がモデルに伝わっていない",
            "fix": "「## 本日の市場概況」「## まとめ」「## 免責事項」を必ず含めてください。",
        }

    if "免責事項" in issues_str:
        return {
            "category": "structure",
            "cause": "免責事項セクションが欠如",
            "hypothesis": "記事末尾の免責事項をモデルが省略した",
            "fix": "記事の最後に「## 免責事項\n\n※本記事は情報提供を目的としており...」を追加してください。",
        }

    if "中国語" in issues_str:
        return {
            "category": "language",
            "cause": "中国語文字が混入している",
            "hypothesis": "モデルの訓練データに中国語が含まれており混入した",
            "fix": "中国語（简体字・繁体字）は絶対に使わないこと。日本語のみで書いてください。",
        }

    return {
        "category": "unknown",
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
    学習済みルールからプロンプト先行注入テキストを生成する。

    優先順位:
      1. 成功パターン（最新3件の最高スコアから特徴を提示）
      2. カテゴリ別ルール（language/title/length/structure）
      3. 高頻度失敗パターン (count > 2) を「要注意」として追加
    """
    parts: list[str] = []

    # 1. 成功パターン（最新3件の最高スコア）
    success = rules.get("success_patterns", [])[-3:]
    if success:
        best = max(success, key=lambda x: x.get("score", 0))
        feat = best.get("features", "")
        if feat:
            parts.append(f"【成功パターン参考】{feat}")

    # 2. カテゴリ別ルール
    for _cat, rule in rules.get("categories", {}).items():
        fix = rule.get("fix", "")
        if fix:
            parts.append(f"- {fix}")

    # 3. 高頻度失敗パターン（count > 2、重複排除）
    existing_text = "\n".join(parts)
    for _key, meta in rules.get("failures", {}).items():
        if not isinstance(meta, dict):
            continue
        if meta.get("count", 0) > 2:
            fix = meta.get("fix", "")
            if fix and fix not in existing_text:
                parts.append(f"- 【要注意】{fix}")
                existing_text += fix

    if not parts:
        return ""
    return "【生成ルール】\n" + "\n".join(parts)


# ---------------------------------------------------------------------------
# 記録
# ---------------------------------------------------------------------------

def record_failure(rules: dict, issue: str, fix: str, category: str = "unknown") -> None:
    """失敗パターンを記録して学習する。剪定も実行。"""
    key = re.sub(r'\s+', '_', issue.strip())[:60]
    entry = rules.setdefault("failures", {}).setdefault(
        key, {"count": 0, "fix": fix, "category": category, "last_seen": ""}
    )
    entry["count"] += 1
    entry["fix"] = fix
    entry["category"] = category
    entry["last_seen"] = datetime.now().isoformat()

    # 失敗カテゴリの使用頻度をカテゴリルールに反映
    if category in rules.get("categories", {}):
        rules["categories"][category]["count"] = \
            rules["categories"][category].get("count", 0) + 1

    prune_rules(rules)


def record_success(rules: dict, content: str, score: int) -> None:
    """
    成功パターンを記録する。
    特徴を自動抽出してプレフィックス生成に活用できる形で保存。
    """
    features: list[str] = []
    if content.startswith("# "):
        features.append("タイトルが# で始まる")
    if len(content) > 2500:
        features.append(f"{len(content)}文字以上")
    elif len(content) > 1500:
        features.append(f"{len(content)}文字")
    if "## 市場概況" in content or "## 本日の市場概況" in content:
        features.append("市場概況セクションあり")
    if "免責事項" in content:
        features.append("免責事項あり")
    if "## まとめ" in content:
        features.append("まとめセクションあり")

    pattern = {
        "score":     score,
        "features":  ", ".join(features),
        "timestamp": datetime.now().isoformat(),
    }
    patterns = rules.setdefault("success_patterns", [])
    patterns.append(pattern)
    rules["success_patterns"] = patterns[-10:]  # 直近10件のみ保持


# ---------------------------------------------------------------------------
# SelfImprovingGenerator
# ---------------------------------------------------------------------------

class SelfImprovingGenerator:
    """
    自己改善ループを持つ記事生成器。

    失敗 → 原因分析(カテゴリ) → 仮説 → プロンプト修正 → 再試行 → 評価 → ルール更新

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
                record_success(self.rules, content, score)
                save_rules(self.rules)
                print(f"  ✅ 自己改善ループ: {attempt + 1}回で成功")
                return content, {"attempts": attempt + 1, "history": history,
                                 "best_attempt": attempt + 1}

            if attempt >= self.max_attempts - 1:
                break

            analysis = analyze_failure(content, issues)
            print(f"  🔍 原因: {analysis['cause']} [category={analysis['category']}]")
            print(f"  💡 仮説: {analysis['hypothesis']}")

            if analysis["fix"]:
                for issue in issues:
                    record_failure(self.rules, str(issue), analysis["fix"],
                                   category=analysis["category"])
                save_rules(self.rules)
                current_prompt = apply_fix(current_prompt, analysis["fix"])
                print(f"  🔧 プロンプト修正: {analysis['fix'][:60]}...")

        best_num = max(history, key=lambda x: (x["score"], x["content_length"]))["attempt"]
        print(f"  ⚠️ 最大試行数到達 → 試行{best_num}の結果(score={best_score})を使用")
        return best_content, {"attempts": self.max_attempts, "history": history,
                               "best_attempt": best_num}

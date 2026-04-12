"""
技術記事自動生成システム。
RAGを使って最新情報を補完しながら
Python・技術ネタの記事を自動生成する。
出力: content/YYYYMMDD_{slug}.md
"""
import re
import json
import unicodedata
from pathlib import Path
from datetime import datetime

AGENT_ROOT   = Path(__file__).parent
CONTENT_DIR  = AGENT_ROOT / "content"          # ルート（後方互換）
PERF_LOG     = AGENT_ROOT / "memory" / "content_log.json"

# =====================================================
# SEOタイトル自動生成
# =====================================================
_RISE_WORDS     = ["急騰", "大幅高", "反発", "上昇"]
_FALL_WORDS     = ["急落", "大幅安", "下落", "反落"]
_ANALYSIS_WORDS = ["背景と今後の戦略", "理由と注目ポイント", "相場分析と注目セクター", "要因と明日への展望"]
_TITLE_HISTORY  = AGENT_ROOT / "memory" / "title_history.json"


def _load_title_history() -> list:
    try:
        return json.loads(_TITLE_HISTORY.read_text(encoding="utf-8"))[-20:]
    except Exception:
        return []


def _save_title_history(pattern: str) -> None:
    history = _load_title_history()
    history.append({"pattern": pattern, "ts": datetime.now().isoformat()})
    _TITLE_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    _TITLE_HISTORY.write_text(
        json.dumps(history[-20:], ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _count_recent_pattern(pattern: str, within: int = 4) -> int:
    """直近N件で同パターンが何回使われたか"""
    return sum(1 for h in _load_title_history()[-within:] if h["pattern"] == pattern)


def _pick_word(words: list, seed: int) -> str:
    return words[seed % len(words)]


def _make_seo_title(topic: str, finance_data: dict) -> str:
    """
    SEO最適化タイトルを投資データから自動生成する。
    - テーマ選択: 原油急変 > VIX急変 > 日経急変 > デフォルト
    - 同パターン4連続で自動切替（重複回避）
    - 朝版（0〜11時）と夕版（12〜23時）で異なるseedを使用
    """
    import hashlib

    # 日付・時間帯からseedを生成（朝夕で異なるパターンを選択）
    now      = datetime.now()
    slot     = "am" if now.hour < 12 else "pm"
    seed_str = now.strftime("%Y%m%d") + slot
    seed     = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)

    # 日付文字列を取得（トピックの（）内、なければ今日）
    m = re.search(r"（(.+?)）", topic)
    date_str = m.group(1) if m else now.strftime("%Y年%m月%d日")

    # 投資データから変動率を抽出
    macro = finance_data.get("macro", {})
    us    = macro.get("us_stocks", {})
    comm  = macro.get("commodities", {})

    vix_chg = us.get("VIX", {}).get("change_pct") or 0.0
    wti_chg = comm.get("WTI原油", {}).get("change_pct") or 0.0

    nikkei_raw = finance_data.get("market_summary", {}).get("nikkei_change", "") or ""
    try:
        nikkei_chg = float(re.sub(r"[^0-9+\-.]", "", nikkei_raw.split("%")[0]))
    except (ValueError, IndexError):
        nikkei_chg = 0.0

    analysis = _pick_word(_ANALYSIS_WORDS, seed)

    # テーマ選択（変動幅 × 重複回避）
    def _can_use(pat: str) -> bool:
        return _count_recent_pattern(pat) < 3

    if abs(wti_chg) >= 3.0 and _can_use("oil"):
        pattern = "oil"
        sign    = f"{wti_chg:+.1f}"
        word    = _pick_word(_FALL_WORDS if wti_chg < 0 else _RISE_WORDS, seed)
        title   = f"【原油{sign}%{word}】日本株への影響と{analysis}（{date_str}）"

    elif abs(vix_chg) >= 7.0 and _can_use("vix"):
        pattern = "vix"
        sign    = f"{vix_chg:+.1f}"
        # VIX上昇=リスクオフ、VIX下落=リスクオン
        mood    = "リスクオフ" if vix_chg > 0 else "リスクオン"
        title   = f"【VIX{sign}%・{mood}】{analysis}（{date_str}）"

    elif abs(nikkei_chg) >= 1.0 and _can_use("nikkei"):
        pattern = "nikkei"
        sign    = f"{nikkei_chg:+.2f}"
        word    = _pick_word(_RISE_WORDS if nikkei_chg >= 0 else _FALL_WORDS, seed)
        title   = f"【日経平均{sign}%{word}】{analysis}（{date_str}）"

    else:
        pattern = "default"
        if abs(nikkei_chg) >= 0.01:
            sign  = f"{nikkei_chg:+.2f}"
            title = f"【日経平均{sign}%】本日の日本株市場まとめと注目ポイント（{date_str}）"
        else:
            title = f"本日の日本株市場まとめと注目ポイント（{date_str}）"

    _save_title_history(pattern)
    return title


def _check_title_content_consistency(title: str, content: str, finance_data: dict) -> list:
    """
    SEOタイトルと記事本文の整合性を確認する。
    タイトルで主張している数値・方向性が記事中に存在するかチェック。
    Returns: 不整合の警告リスト（空なら問題なし）
    """
    warnings = []

    # 原油タイトルの場合: 記事に「原油」「WTI」が含まれているか
    if "原油" in title and re.search(r"[+-]\d+\.\d+%", title):
        if not re.search(r"原油|WTI", content):
            warnings.append("SEOタイトルに「原油」があるが記事本文に原油の言及なし")

    # VIXタイトルの場合: 記事に「VIX」が含まれているか
    if "VIX" in title and re.search(r"[+-]\d+\.\d+%", title):
        if not re.search(r"VIX", content):
            warnings.append("SEOタイトルに「VIX」があるが記事本文にVIXの言及なし")

    # 日経平均タイトルの場合: 方向性チェック
    m = re.search(r"日経平均([+-]\d+\.\d+)%", title)
    if m:
        title_chg = float(m.group(1))
        # 上昇タイトルなのに記事で急落と書いていないか（逆方向チェック）
        if title_chg > 0 and re.search(r"日経.{0,5}急落|大幅.{0,3}下落", content):
            warnings.append(f"SEOタイトルは日経+{title_chg:.2f}%なのに記事に「急落」表現あり")
        elif title_chg < 0 and re.search(r"日経.{0,5}急騰|大幅.{0,3}上昇", content):
            warnings.append(f"SEOタイトルは日経{title_chg:.2f}%なのに記事に「急騰」表現あり")

    return warnings


def _check_nikkei_consistency(content: str, nikkei_actual: float) -> str:
    """
    記事内の日経平均数値を実際の終値に完全統一する。
    日経平均の範囲（10,000〜100,000円）内かつ実際値と1%以上乖離している数値を置換する。
    """
    if nikkei_actual <= 0:
        return content

    actual_str = f"{nikkei_actual:,.2f}"

    # カンマあり（38,500.11）またはカンマなし5桁（38500）
    pattern = r'(?<!\d)(\d{2},\d{3}(?:\.\d{1,2})?|\d{5}(?:\.\d{1,2})?)(?=\s*(?:円|円台|ドル台|ポイント)?)'

    def is_nikkei_range(val: float) -> bool:
        return 10000 <= val <= 100000

    def replace_nikkei(m: re.Match) -> str:
        val_str = m.group(1).replace(',', '')
        try:
            val = float(val_str)
        except ValueError:
            return m.group(0)
        if is_nikkei_range(val) and abs(val - nikkei_actual) / nikkei_actual > 0.01:
            print(f"  🔢 日経数値修正: {m.group(1)} → {actual_str}")
            return actual_str
        return m.group(0)

    return re.sub(pattern, replace_nikkei, content)


_AFFILIATE_CONFIG = AGENT_ROOT / "config" / "affiliate_config.json"


def _build_affiliate_footer() -> str:
    """アフィリエイトセクションを記事末尾（免責事項直前）に追加する"""
    import random as _random
    try:
        cfg = json.loads(_AFFILIATE_CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return ""

    amazon_books  = cfg.get("amazon", {}).get("books", [])
    amazon_apple  = cfg.get("amazon", {}).get("apple", [])
    rakuten_books = cfg.get("rakuten", {}).get("books", [])

    sections = []

    # 投資本セクション
    if rakuten_books or amazon_books:
        section = "## 📚 おすすめの書籍\n\n"
        # 楽天ウィジェット（HTMLそのまま埋め込み）
        if rakuten_books:
            book = _random.choice(rakuten_books)
            section += book["html"] + "\n\n"
        # AmazonリンクはMarkdown形式
        if amazon_books:
            book = _random.choice(amazon_books)
            section += f"**[{book['title']}（Amazon）]({book['url']})**\n\n{book['desc']}\n\n"
        section += "---"
        sections.append(section)

    # Appleガジェット
    if amazon_apple:
        item = _random.choice(amazon_apple)
        sections.append(
            f"## 💻 ガジェット系\n\n"
            f"快適な投資環境を整えるために：\n\n"
            f"**[Amazonで見る]({item['url']})**\n\n"
            f"---"
        )

    return "\n\n".join(sections)


# ジャンル別サブディレクトリ
CONTENT_DIRS = {
    "finance_news": AGENT_ROOT / "content" / "finance",
    "python_tips":  AGENT_ROOT / "content" / "tech",
    "ai_tools":     AGENT_ROOT / "content" / "tech",
    "library_intro":AGENT_ROOT / "content" / "tech",
    "automation":   AGENT_ROOT / "content" / "tech",
    "ai_news":      AGENT_ROOT / "content" / "tech",
    "arxiv_ai":     AGENT_ROOT / "content" / "tech",
    "security":     AGENT_ROOT / "content" / "tech",
    "science":      AGENT_ROOT / "content" / "general",
    "food":         AGENT_ROOT / "content" / "general",
    "gadget":       AGENT_ROOT / "content" / "general",
}


def get_content_dir(genre_id: str) -> Path:
    """ジャンルに対応するコンテンツ保存ディレクトリを返す（なければ作成）"""
    base = CONTENT_DIRS.get(genre_id, AGENT_ROOT / "content" / "general")
    base.mkdir(parents=True, exist_ok=True)
    return base

# 技術記事のジャンル定義
TECH_GENRES = [
    {
        "id":       "python_tips",
        "label":    "Python実践テクニック",
        "queries":  ["Python tips 2026", "Python best practices"],
        "template": "tips",
    },
    {
        "id":       "ai_tools",
        "label":    "AIツール活用法",
        "queries":  ["AI agent tool 2026", "LLM automation Python"],
        "template": "tutorial",
    },
    {
        "id":       "library_intro",
        "label":    "Pythonライブラリ紹介",
        "queries":  ["Python new library 2026", "Python productivity tool"],
        "template": "introduction",
    },
    {
        "id":       "automation",
        "label":    "Python自動化",
        "queries":  ["Python automation script 2026", "Python workflow automation"],
        "template": "tutorial",
    },
    {
        "id":      "finance_news",
        "label":   "投資・市場情報",
        "queries": ["日本株 市況", "株主優待 最新"],
        "template": "finance",
    },
]

# 全テンプレートに適用する品質ルール
_QUALITY_RULES = """
【絶対条件】
- 必ず最初の行を「# 記事タイトル」の形式で始めること（例: # Pythonで並列処理を実装する3つの方法）
- 最低1500文字以上で書くこと（これより短い場合は失敗とみなす）
- ## 見出しを最低3つ以上含めること
- コード例（```python）を最低2つ以上含めること
- 記事と無関係なコード（Flask、JWT等）は絶対に含めないこと

【品質ルール（必ず守ること）】
1. プレースホルダー禁止: 「よくある質問1」「回答」のような仮の内容は絶対に書かない
2. 繰り返し禁止: 同じコード例や説明を複数セクションで繰り返さない
3. 具体性必須: 全てのコード例は実際に動作する具体的なコードにする
4. FAQ必須: 実際に初心者が疑問に思う具体的な質問と回答を3〜5個書く
5. 比較必須（比較記事の場合）: 表形式での比較を必ず含める
6. 文字数: 2500文字以上を目標にする

"""

# Zenn用テンプレート（概要・軽め・1200〜1800文字）
ZENN_TEMPLATE = """
【絶対条件】
- 必ず最初の行を「# 記事タイトル」で始めること
- 1200〜1800文字（読みやすい長さ）
- ## 見出しを3つ以上
- コード例を1〜2個（シンプルなもの）
- 最後に「## まとめ」を含める

以下の情報を使って、Zennエンジニア向けの概要記事を日本語で書いてください。
トピック: {topic}
参考情報:
{context}

記事の構成:
# {topic}
## はじめに（このライブラリ/技術とは）
（2〜3文で概要）
## 基本的な使い方
（シンプルなコード例1つ）
## 実践例
（もう少し実用的なコード例）
## まとめ
（3〜5点の箇条書き）

制約:
- シンプルで読みやすく
- 初心者でも理解できる
- 深い応用は「詳細記事（はてなブログ）」に誘導する
"""

# はてな用テンプレート（詳細・深め・3000文字以上）
HATENA_TEMPLATE = """
【絶対条件】
- 必ず最初の行を「# 記事タイトル」で始めること
- 3000文字以上（詳細で実践的）
- ## 見出しを5つ以上
- コード例を3個以上（応用・実務レベル）
- トラブルシューティングセクションを含める
- FAQを3〜5個含める

以下の情報を使って、実務エンジニア向けの詳細解説記事を日本語で書いてください。
トピック: {topic}
参考情報:
{context}

記事の構成:
# {topic} 完全ガイド
## はじめに
（2〜4文で以下を全て含めること）
- この記事が誰向けか（例: Pythonで○○を実装したいエンジニア向け）
- 読み終えると何ができるようになるか
- 概要だけ知りたい方はZennの記事もあわせてご覧ください、という案内を自然な文章で含める
## この記事でわかること
（箇条書き5点・具体的に）
## 環境準備
（インストール・セットアップ）
## 基礎実装
（ステップバイステップのコード例）
## 応用パターン
（実務で使えるコード例）
## パフォーマンス最適化・ベストプラクティス
（上級者向けのポイント）
## トラブルシューティング
（よくあるエラーと対処法3件以上）
## FAQ
（実際に初心者が疑問に思う質問3〜5個）
## まとめ
（実践的な判断基準を含む箇条書き）

制約:
- 実務で使える詳細な内容
- コードは全て動作するものを
- 「Zennに概要版あり」と冒頭で触れる
"""

# Zenn用投資記事（概要）
ZENN_FINANCE_TEMPLATE = """
あなたは日本の金融アナリストです。
日本語ネイティブとして自然で専門的な文章を書いてください。

【絶対条件】
- 必ず最初の行を「# 記事タイトル」で始めること
- 1500文字以上
- ## 見出しを4つ以上
- 免責事項を末尾に含める

以下の市場データを使って、投資家向けの市況解説記事を日本語で書いてください。
トピック: {topic}
市場データ:
{context}

記事の構成:
# {topic}
## 本日の市場概況
（日経平均の動きを数値で紹介。なぜその動きになったか因果関係を必ず説明する）
## 本日の注目ニュース
（ニュースを3〜5件紹介。各ニュースに「なぜ重要か」の1行コメントを添える）
## 値動きのポイント
【出力フォーマット（必ずこの形式で書くこと）】
値上がり上位:
- 銘柄名（変動率）
  - 関連ニュース: [コンテキストの「値動き銘柄の関連ニュース」に記載がある場合のみ。なければ「関連ニュースなし」]
  - 背景: [コンテキストに明確な根拠がある場合のみ。なければ「背景は未公表」]
値下がり上位:（同様のフォーマット）
【禁止事項】
- 「〜の期待が背景」「〜の可能性がある」等の推測表現は禁止
- コンテキストにない理由・背景を書くことは禁止
- 必ず「背景は未公表」か「関連ニュース: [タイトル]」のどちらかを選ぶ
## 本日の市場のポイント（3つ）
（本日の市場を象徴する重要ポイントを3つ箇条書きで）
## まとめ

---
⚠️ 免責事項: この記事は情報提供を目的としており、投資助言ではありません。
投資判断はご自身の責任で行ってください。

【厳守ルール】
- 特定銘柄の売買を推奨しない
- 因果関係を必ず説明する（「〜のため」「〜を受けて」）
- 日本語のみ（中国語・英語の混入絶対禁止）
- 提供データ外の企業名・数値を補完しない
- 「よくある質問1」等のプレースホルダー禁止
- コンテキストにないニュース・企業名を補完しない
- 上昇・下落の理由は「[重要:最優先] 本日の市場変動の主因候補」セクションの情報を使う
- 上昇理由が不明な場合は「背景は複合的な要因によるものと推測される」と書く
- 「米中関係」「ホルムズ海峡」「地政学」等はコンテキストにある場合のみ書く
- 各銘柄の値動き理由が不明な場合は「具体的な背景は公表されていない」と書く
- 前日比は必ず市場データの「前日比」の値を使う（例: +1497.34(+2.87%)）
- 【VIXの記述ルール（厳守）】コンテキストの「VIX:【VIXは上昇】」または「【VIXは下落】」を確認する
  - VIXが上昇している場合:「市場の不安感が高まった」「VIXが上昇した」と書く
  - VIXが下落している場合:「市場の不安感が緩和した」「VIXが低下した」と書く
  - 方向性を間違えると整合性エラーになるため必ず確認すること

【文体ルール（最重要）】
- 全文をですます体（〜します・〜しました・〜です）に統一する
- 「〜した。」「〜なった。」等の普通体で文を終えない（必ずですます体にする）
- 「〜した（背景は未公表）」のような文末への括弧挿入は禁止
- 「背景は未公表」は値動きのポイントセクションのみ使用可・1記事で最大3回まで
- 「詳細は未公表」は使用禁止（代わりに文章から省略する）
- 「〜ことを意味します」→「〜を示しています」に言い換える
- 「〜に寄与しました」→「〜に影響しました」「〜を押し下げました」
- 「〜が確認されました」→「〜が発表されました」「〜が報じられました」
"""

# はてな用投資記事（詳細）
HATENA_FINANCE_TEMPLATE = """
あなたは日本の金融アナリストです。
日本語ネイティブとして自然で専門的な文章を書いてください。

【絶対条件】
- 必ず最初の行を「# 記事タイトル」で始めること
- 2500文字以上
- ## 見出しを7つ以上
- 免責事項を末尾に含める

以下の市場データを使って、投資家向けの詳細な市況解説記事を日本語で書いてください。
トピック: {topic}
市場データ:
{context}

記事の構成:
# {topic} - 詳細解説
## はじめに
（本日の市場の概要。1〜2段落で簡潔に）
## 本日の市場概況
（日経平均の数値と前日比を記載。上昇・下落理由は「主因候補」セクションの情報を使う。
VIXが高水準かつ株価上昇の場合は「株価は上昇したが市場の警戒感は継続」と説明。
VIXが低下した場合は「リスクオン傾向が顕著」と説明。VIXと株価の方向性を矛盾なく記述する。
上昇・下落の説明は必ず因果連鎖で記述すること（単体説明禁止）:
例: 「VIX低下 → 投資家心理が改善 → グロース株に資金流入 → 日経平均を押し上げた」
例: 「原油急落 → エネルギーコスト低下期待 → インフレ懸念緩和 → 金利低下観測 → 株式バリュエーション拡大」
2〜3段階の連鎖で記述すること）
## 🌏 マクロ経済環境
（為替・米国株・原油・VIXの数値と変動率を記載。各数値が日本市場に与える影響を因果関係で説明。
VIXの解釈はコンテキストの「→恐怖感」注釈を参照すること。
各指標の説明後に「だから資金はどこへ」を必ず記述:
・円安進行 → 輸出関連・自動車セクターに資金流入しやすい
・VIX低下 → グロース株・小型株への資金回帰が起きやすい
・原油下落 → 航空・運輸・化学セクターへの追い風
実際のデータに合わせて適宜変形して記述すること）
## 本日の注目ニュース
（ニュースを3〜5件紹介。各ニュースに「なぜ重要か」「どんな影響があるか」を説明）
## 値上がり・値下がりランキング解説
【出力フォーマット（必ずこの形式で書くこと）】
値上がり上位:
- 銘柄名（変動率）
  - 関連ニュース: [コンテキストの「値動き銘柄の関連ニュース」に記載がある場合のみ。なければ「関連ニュースなし」]
  - 背景: [コンテキストに明確な根拠がある場合のみ。なければ「背景は未公表」]
値下がり上位:（同様のフォーマット）
【禁止事項】
- 「〜の期待が背景」「〜の可能性がある」等の推測表現は禁止
- コンテキストにない理由・背景を書くことは禁止
- 必ず「背景は未公表」か「関連ニュース: [タイトル]」のどちらかを選ぶ
## ⚖️ 法務・規制動向
（行政処分・訴訟情報があれば紹介。なければ「本日は特筆すべき情報はありませんでした」）
## 📊 本日の市場のポイント（3つ）
（本日の市場を象徴する重要ポイントを3つ。必ず因果関係を含める）
## 📈 明日の戦略
（以下の4項目を必ず記述。断定禁止・「〜が意識されやすい」「〜の可能性」で記述）
・基本シナリオ: 〜継続 or 〜転換の可能性（データに基づき記述）
・狙い: 押し目候補セクター / 継続注目セクター
・回避: 材料なし急騰銘柄・過熱感のある銘柄
・危険シナリオ: VIX反発時 / 円高転換時の影響を記述
## 🎯 注目テーマ
（以下の条件で記述）
・コンテキストに含まれる銘柄・業種のみ使用
・「〜に資金が集まりやすい局面」「〜テーマが注目される」等の表現のみ
・売買推奨・目標株価は絶対に書かない
・3〜5項目を箇条書きで記述
## 今後の注目点
（来週以降に向けた市場の見どころを客観的に記述）
## FAQ
（以下の条件で3〜5個のQ&Aを作成する:
- 質問は「本日のコンテキストデータ」に基づく内容のみ
- 具体的な例:「Q. 本日なぜ日経平均が上昇したのですか？」「Q. VIXが下落すると何を意味しますか？」「Q. 原油価格の下落は日本株にどう影響しますか？」
- コンテキストに含まれないニュース・企業名をFAQに使わない
- 回答は100文字以内で簡潔に
- 「よくある質問1」等のプレースホルダー禁止
- 日本語のみ）
## 📊 この上昇は続くのか？
（以下のロジックで必ず記述する。断定禁止・「〜と見られる」「〜の可能性が高い」で記述）
・VIXが20以下かつ下落中 → 「リスクオン継続の可能性が高い」
・VIXが20以上かつ上昇中 → 「短期資金主導のため持続性に注意」
・円安継続中 → 「輸出関連を中心に下値は堅い」
・円高転換 → 「輸出関連に注意が必要」
## まとめ

---
⚠️ 免責事項: この記事は情報提供を目的としており、
投資勧誘・投資助言ではありません。
投資判断はご自身の責任で行ってください。

【厳守ルール】
- 特定銘柄の売買を推奨しない
- 因果関係を必ず説明する（「〜のため」「〜を受けて」「〜が影響して」）
- 日本語のみ（中国語・英語の混入絶対禁止）
- 提供データ外の企業名・数値を補完しない
- 「よくある質問1」等のプレースホルダー禁止
- 「〜の可能性がある」「〜と見られる」等の推定表現を使う
- 同じ表現（「不動産市場の悪化」等）を複数セクションで繰り返さない
- 各セクションは独立した内容を書く
- コンテキストに含まれないニュース・企業名・事件を書かない
- 上昇・下落の理由は「[重要:最優先] 本日の市場変動の主因候補」セクションの情報を使う
- 上昇理由が不明な場合は「背景は複合的な要因によるものと推測される」と書く
- 「米中関係」「ホルムズ海峡」「地政学」等はコンテキストにある場合のみ書く
- 各銘柄の値動き理由が不明な場合は「具体的な背景は公表されていない」と書く
- 前日比は必ず市場データの「前日比」の値を使う（例: +1497.34(+2.87%)）
- 【VIXの記述ルール（厳守）】コンテキストの「VIX:【VIXは上昇】」または「【VIXは下落】」を確認する
  - VIXが上昇している場合:「市場の不安感が高まった」「VIXが上昇した」と書く
  - VIXが下落している場合:「市場の不安感が緩和した」「VIXが低下した」と書く
  - 方向性を間違えると整合性エラーになるため必ず確認すること

【文体ルール（最重要）】
- 全文をですます体（〜します・〜しました・〜です）に統一する
- 「〜した。」「〜なった。」等の普通体で文を終えない（必ずですます体にする）
- 「〜した（背景は未公表）」のような文末への括弧挿入は禁止
- 「背景は未公表」は値動きのポイントセクションのみ使用可・1記事で最大3回まで
- 「詳細は未公表」は使用禁止（代わりに文章から省略する）
- 「〜ことを意味します」→「〜を示しています」に言い換える
- 「〜に寄与しました」→「〜に影響しました」「〜を押し下げました」
- 「〜が確認されました」→「〜が発表されました」「〜が報じられました」
"""

# 記事テンプレート
ARTICLE_TEMPLATES = {
    "tips": """
以下の情報を使って、Pythonエンジニア向けの実践的なtips記事を日本語で書いてください。
トピック: {topic}
参考情報:
{context}
記事の構成:
# {topic}
## はじめに
（なぜこのテクニックが重要か、2〜3文）
## 基本的な使い方
（コード例付きで説明）
## 実践例
（実際のユースケースとコード例）
## 応用テクニック
基本の使い方を理解した上で、実務でよく使われる
上級者向けのパターンやテクニックを説明してください。
基本的な使い方の繰り返しではなく、
実務で役立つ発展的な内容にすること。
コード例を必ず含めること。
## いつ使うべきか（使い分けガイド）
以下の観点で使い分けを表形式で示してください（該当する場合）。
具体的な比較表を含めること。
## まとめ
この記事で学んだことを5点以上の箇条書きにまとめてください。
単なる特徴の羅列ではなく、「〜する場合は〜を使う」という
実践的な判断基準を含めること。
## FAQ
このトピックに関してよくある疑問を3〜5個、具体的に考えて
Q&A形式で書いてください。
「よくある質問1」のようなプレースホルダーは絶対に使わないこと。
実際に初心者が疑問に思うことを具体的に書くこと。
制約:
- 2500文字以上
- コード例を必ず含める
- 日本語で書く
- Markdownフォーマット
""",
    "tutorial": """
以下の情報を使って、Pythonエンジニア向けのチュートリアル記事を日本語で書いてください。
トピック: {topic}
参考情報:
{context}
記事の構成:
# {topic}
## この記事でわかること
（箇条書き3〜5点）
## 環境準備
（必要なライブラリのインストール方法）
## ステップ1: 基礎実装
（コード例付き）
## ステップ2: 機能追加
（基礎実装とは別の新しいコード例付き）
## ステップ3: 実用化
（完成コードと説明）
## トラブルシューティング
実際によく起きるエラーと具体的な対処法を3件以上書くこと。
「エラー例1」のようなプレースホルダーは使わないこと。
## FAQ
このトピックに関してよくある疑問を3〜5個、具体的に考えて
Q&A形式で書いてください。
実際に初心者が疑問に思うことを具体的に書くこと。
## まとめ
制約:
- 2500文字以上
- 各ステップにコード例を含める
- 日本語で書く
- Markdownフォーマット
""",
    "introduction": """
以下の情報を使って、Pythonライブラリの紹介記事を日本語で書いてください。
トピック: {topic}
参考情報:
{context}
記事の構成:
# {topic}
## このライブラリとは
（概要と特徴）
## インストール方法
```bash
pip install xxx
```
## 基本的な使い方
（コード例付き）
## 実践サンプル
（実際に使えるコード例）
## 類似ライブラリとの比較
具体的なライブラリ名を挙げて表形式で比較してください。
| 観点 | このライブラリ | 代替ライブラリ |
のような表を必ず含めること。
## FAQ
このトピックに関してよくある疑問を3〜5個、具体的に考えて
Q&A形式で書いてください。
実際に初心者が疑問に思うことを具体的に書くこと。
## まとめ
この記事で学んだことを5点以上の箇条書きにまとめてください。
「〜する場合は〜を使う」という実践的な判断基準を含めること。
制約:
- 2500文字以上
- 実用的なコード例を必ず含める
- 日本語で書く
- Markdownフォーマット
""",
}


# --- QUALITY FILTER START ---
_REJECTION_PATTERNS = [
    "ご指摘ありがとうございます",
    "申し訳ありません",
    "I cannot",
    "I'm unable",
    "不適切なリクエスト",
    "作成することができません",
]


def _quality_check(content: str) -> tuple:
    """
    記事の品質をチェックする。
    Returns: (passed: bool, reason: str)
    """
    # LLM拒否パターンを冒頭200文字で検出
    head = content[:200] if content else ""
    for pattern in _REJECTION_PATTERNS:
        if pattern in head:
            return False, f"LLM拒否パターン検出: 「{pattern}」"

    if not content or len(content) < 1500:
        return False, f"文字数不足: {len(content) if content else 0}文字（最低1500文字）"
    # 最初の非空行が # タイトルであることを確認
    first_line = next((l for l in content.split("\n") if l.strip()), "")
    if not first_line.startswith("# "):
        return False, f"タイトル行なし（最初の行が '# 記事タイトル' 形式でない）: {first_line[:50]!r}"
    heading_count = content.count("\n## ")
    if heading_count < 3:
        return False, f"見出し不足: {heading_count}個（最低3個）"
    if "```python" not in content and "```bash" not in content:
        return False, "コードブロックなし（最低1個必要）"
    if not re.search(r'^##\s+.*まとめ', content, re.MULTILINE):
        return False, "まとめセクションなし"
    return True, "OK"
# --- QUALITY FILTER END ---


# --- CJK FILTER START ---
_ZH_REPLACEMENTS = {
    "网络": "ネットワーク",
    "环境": "環境",
    "连接": "接続",
    "安装": "インストール",
    "运行": "実行",
    "错误": "エラー",
    "程序": "プログラム",
    "文件": "ファイル",
    "数据": "データ",
    "系统": "システム",
    "接口": "インターフェース",
    "库": "ライブラリ",
    "模型": "モデル",
    "语言": "言語",
    "代码": "コード",
    "功能": "機能",
    "方法": "メソッド",
    "类": "クラス",
    "对象": "オブジェクト",
    "变量": "変数",
}

_ZH_DETECT_PATTERNS = [
    "网络", "环境", "连接", "安装", "运行", "错误",
    "程序", "文件", "数据", "系统", "接口",
]


def _remove_chinese_chars(text: str) -> str:
    """
    中国語・韓国語・異常文字を除去または日本語に置換する。
    qwen系モデルが中国語・韓国語を混入するバグへの対策。
    注意: 中国語と日本語漢字は同一 Unicode ブロック (U+4E00-9FFF) を共有するため
          中国語固有の既知単語を辞書置換する方式を採用（一括除去は NG）。
    """
    # 既知の中国語単語を日本語に置換（辞書ベース）
    for zh, ja in _ZH_REPLACEMENTS.items():
        text = text.replace(zh, ja)
    # 韓国語（ハングル）は日本語と別 Unicode ブロックなので安全に除去可能
    text = re.sub(r'[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]', '', text)
    # 中国語の疑問詞パターンを除去（什么様・什么样 等）
    text = re.sub(r'什[^\s]{0,3}[様样]', '', text)      # 什么様・什么样
    text = re.sub(r'[为為][^\s]{0,3}[么麼]', '', text)  # 为什么
    text = re.sub(r'[样]的', '', text)                   # 样的
    text = re.sub(r'这[个個]', '', text)                 # 这个
    text = re.sub(r'那[个個]', '', text)                 # 那个
    # 地政学・情勢系の中国語表現
    text = re.sub(r'地[缘緣]政治的?', '地政学的', text)  # 地缘政治→地政学的
    text = re.sub(r'地[缘緣]', '', text)                 # 地缘
    text = re.sub(r'牵[涉摂]', '', text)                 # 牵涉
    text = re.sub(r'紧[張张]', '緊張', text)             # 紧张→緊張
    # 簡体字動詞・形容詞
    text = re.sub(r'发[展展]', '発展', text)             # 发展→発展
    text = re.sub(r'进[行行]', '進行', text)             # 进行→進行
    text = re.sub(r'经[济濟]', '経済', text)             # 经济→経済
    text = re.sub(r'[认認]为', 'と考える', text)         # 认为→と考える
    text = re.sub(r'[从從][而]', 'そのため', text)       # 从而→そのため
    text = re.sub(r'[对對][于於]', 'に対して', text)     # 对于→に対して
    text = re.sub(r'[关關][于於]', 'について', text)     # 关于→について
    # 全角英数字を半角に変換
    text = text.translate(str.maketrans(
        'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ'
        'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ'
        '０１２３４５６７８９',
        'abcdefghijklmnopqrstuvwxyz'
        'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        '0123456789'
    ))
    # 連続する空白・改行を整理
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


def _quality_check_v2(content: str, min_chars: int = 1500, require_code: bool = True,
                      genre_id: str = "") -> tuple:
    """品質チェック + 中国語文字検出 + f-string未展開検出

    finance_news は文字数ではなく情報密度でチェックする。
    技術記事は従来通り文字数・コードブロックでチェックする。
    """
    if not content:
        return False, "空のコンテンツ"

    # LLM拒否パターン（最優先）
    head = content[:200]
    for pattern in _REJECTION_PATTERNS:
        if pattern in head:
            return False, f"LLM拒否パターン検出: 「{pattern}」"

    # タイトル行チェック（共通）
    first_line = next((l for l in content.split("\n") if l.strip()), "")
    if not first_line.startswith("# "):
        return False, f"タイトル行なし（最初の行が '# 記事タイトル' 形式でない）: {first_line[:50]!r}"

    if genre_id == "finance_news":
        # --- 投資記事: 情報密度チェック ---
        issues = []
        # 必須セクション
        for section in ("市場概況", "明日の戦略", "注目テーマ", "上昇は続くのか", "まとめ"):
            if section not in content:
                issues.append(f"必須セクションなし:「{section}」")
        # 日経平均の数値（3〜6万円台、小数なし形式も許可）
        if not re.search(r'[3-6][0-9],[0-9]{3}(?:\.[0-9]+)?', content):
            issues.append("日経平均の数値が見つかりません")
        # 免責事項
        if "免責事項" not in content:
            issues.append("免責事項なし")
        # 極端に短い場合のみNG
        if len(content) < 800:
            issues.append(f"内容が極端に少ない: {len(content)}文字")
        if issues:
            return False, " / ".join(issues)
    else:
        # --- 技術記事: 従来の文字数チェック ---
        if len(content) < min_chars:
            return False, f"文字数不足: {len(content)}文字（最低{min_chars}文字）"
        passed, reason = _quality_check(content)
        if not passed and reason.startswith("文字数不足"):
            passed = True
            reason = "OK"
        if not passed and not require_code and "コードブロックなし" in reason:
            passed = True
            reason = "OK"
        if not passed:
            return passed, reason
    found = [p for p in _ZH_DETECT_PATTERNS if p in content]
    if found:
        return False, f"中国語文字が混入: {found}"
    # 中国語特有パターン検出（什么様・什么样・为什么・地缘政治 等）
    chinese_patterns = re.findall(
        r'什[^\s]{0,3}[様样]|[为為][^\s]{0,3}[么麼]|[样]的|这[个個]|那[个個]'
        r'|地[缘緣]政治|地[缘緣]|牵[涉摂]|紧[張张]|经[济濟]|[认認]为',
        content
    )
    if chinese_patterns:
        return False, f"中国語パターン検出: {''.join(chinese_patterns[:3])}"
    # 韓国語（ハングル）チェック
    korean = re.findall(r'[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]{2,}', content)
    if korean:
        return False, f"韓国語が混入: {''.join(korean[:3])}"
    # コードブロックを除いた本文でf-string未展開チェック
    no_code = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    fstring_hits = re.findall(r"\{[a-z_]+[\.\[][^}\n]{1,40}\}", no_code)
    if fstring_hits:
        return False, f"f-string未展開が混入: {fstring_hits[:3]}"
    return True, "OK"
# --- CJK FILTER END ---


_NORMALIZE_PATTERNS = [
    (r'背景は不明(?!確)', '背景は未公表'),      # 「背景は不明確」は次のパターンへ
    (r'背景は不明確(?!認)', '背景は未公表'),   # 「背景は不明確認」は除外
    (r'明確な理由はなし', '背景は未公表'),
    (r'特段の材料なし', '背景は未公表'),
    (r'明確な要因はなし', '背景は未公表'),
    (r'具体的な背景は公表されていない', '背景は未公表'),
    (r'具体的な背景は不明', '背景は未公表'),
    (r'詳細は不明', '背景は未公表'),
    (r'背景情報なし', '背景は未公表'),
    # 曖昧な推測表現を直接置換
    (r'と考えられます', 'と見られます'),
    (r'と推測されます', 'と見られます'),
    (r'影響していると見られる', '影響していると見られ'),
    (r'要因と推測される', '要因と見られます'),
    (r'背景にあると見られる', '背景にあると見られます'),
    (r'影響を与えたと考えられる', '影響を与えたと見られます'),
    # 行単位でのみ置換（「本日は関連ニュースなしの銘柄が多く」等の誤爆防止）
    (r'(?m)^関連ニュースなし$', '関連ニュース: なし'),
]


def _normalize_stock_expressions(content: str) -> str:
    """銘柄説明の表現を統一する（「背景は不明」→「背景は未公表」等）"""
    for pattern, replacement in _NORMALIZE_PATTERNS:
        content = re.sub(pattern, replacement, content)
    return content


# 文体統一の後処理パターン
_STYLE_NORMALIZE_PATTERNS = [
    # 「詳細は未公表」「背景は未公表」の括弧挿入を削除
    (r'（詳細は未公表）', ''),
    (r'（背景は未公表）', ''),
    (r'（関連は未確認）', ''),
    (r'\(詳細は未公表\)', ''),
    # 機械的表現を自然な表現に
    (r'ことを意味します', 'ことを示しています'),
    (r'ことを意味し、', 'ことを示しており、'),
    (r'に寄与しました', 'に影響しました'),
    (r'に寄与した', 'に影響した'),
    (r'が確認されました', 'が報告されています'),
    (r'が確認され', 'が報告され'),
    # 文体混在の修正（普通体→丁寧体）
    (r'となった。', 'となりました。'),
    (r'進んだ。', '進みました。'),
    (r'下落した。', '下落しました。'),
    (r'上昇した。', '上昇しました。'),
    (r'影響した。', '影響しました。'),
    (r'広がった。', '広がりました。'),
    (r'続いた。', '続きました。'),
    (r'強まった。', '強まりました。'),
    (r'弱まった。', '弱まりました。'),
    (r'高まった。', '高まりました。'),
    (r'低下した。', '低下しました。'),
    (r'上回った。', '上回りました。'),
    (r'下回った。', '下回りました。'),
    (r'見られた。', '見られました。'),
    (r'なった。', 'なりました。'),
]


def _normalize_style(content: str) -> str:
    """文体を統一する後処理（ですます体への統一・機械的表現の除去）"""
    result = content

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ⓪ タイトル行正規化（プリアンブル・異形式対応）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    _lines = result.split('\n')

    # (a) 先頭のプリアンブル行をスキップ
    _skip_patterns = [
        r'^（ここ',
        r'^\.\.\.',
        r'^We need',
        r'^We have',
        r'^We (are|will|can|should)',
        r'^The\s+user',
        r'^The\s+following',
        r'^Here\s+(is|are|we)',
        r'^以下の条件',
        r'^\*\*質問',
        r'^\*\*実装',
        r'^---\s*$',
        r'^【質問】',
        r'^Theuser',
    ]
    while _lines and any(
        re.match(p, _lines[0].strip()) for p in _skip_patterns
    ):
        _lines.pop(0)

    # (b) 最初の非空行がタイトル異形式なら # 形式に正規化
    if _lines:
        _first = _lines[0].strip()
        _replaced = False

        # **記事タイトル:** XXX  /  **タイトル**: XXX  /  #**タイトル**:XXX
        _m = re.match(
            r'^\*{0,2}#?\s*(?:記事タイトル|タイトル)[：:]\s*\*{0,2}\s*(.+)',
            _first
        )
        if _m:
            _lines[0] = f"# {_m.group(1).strip('*').strip()}"
            _replaced = True

        # **# XXX**  /  **#XXX**
        if not _replaced:
            _m2 = re.match(r'^\*+#\s*(.+?)\**$', _first)
            if _m2:
                _lines[0] = f"# {_m2.group(1).strip()}"
                _replaced = True

        # **XXX** （太字のみ・タイトルっぽい長さ）
        if not _replaced:
            _m3 = re.match(r'^\*\*(.{5,50})\*\*\s*$', _first)
            if _m3 and '：' not in _m3.group(1) and ':' not in _m3.group(1):
                _lines[0] = f"# {_m3.group(1).strip()}"

    result = '\n'.join(_lines)

    # ① 括弧内の「未公表」「未確認」系を完全削除（全角・半角両対応）
    result = re.sub(r'[（(][^）)]*未公表[^）)]*[）)]', '', result)
    result = re.sub(r'[（(][^）)]*未確認[^）)]*[）)]', '', result)

    # ② ランキングセクション外の「背景は未公表」を削除
    in_ranking = False
    lines = result.split('\n')
    cleaned = []
    for line in lines:
        if re.search(r'値上がり|値下がり|ランキング解説', line):
            in_ranking = True
        elif line.startswith('## ') and in_ranking:
            in_ranking = False

        if '背景は未公表' in line and not in_ranking:
            # 箇条書き形式「- 背景は未公表〜。」も丸ごと除去
            line = re.sub(r'\s*[-・]\s*背景は未公表[^。\n]*[。、]?', '', line)
            # 文中・文末の「背景は未公表〜。」（「です。」「と見られます。」等の後続も含む）を除去
            line = re.sub(r'背景は未公表[^。\n]*[。、]?', '', line)
        cleaned.append(line)
    result = '\n'.join(cleaned)

    # ③ 機械的表現の置換（_STYLE_NORMALIZE_PATTERNSを内包）
    replacements = [
        # 括弧付き未公表（①で取りこぼした場合の保険）
        (r'（詳細は未公表）', ''),
        (r'（背景は未公表）', ''),
        (r'（関連は未確認）', ''),
        # 機械的表現
        (r'ことを意味します', 'ことを示しています'),
        (r'ことを意味し、', 'ことを示しており、'),
        (r'に寄与しました', 'に影響しました'),
        (r'に寄与した', 'に影響した'),
        (r'が確認されました', 'が報告されています'),
        (r'が確認され', 'が報告され'),
        # 普通体→ですます体
        (r'となった。', 'となりました。'),
        (r'進んだ。', '進みました。'),
        (r'下落した。', '下落しました。'),
        (r'上昇した。', '上昇しました。'),
        (r'影響した。', '影響しました。'),
        (r'広がった。', '広がりました。'),
        (r'続いた。', '続きました。'),
        (r'強まった。', '強まりました。'),
        (r'弱まった。', '弱まりました。'),
        (r'高まった。', '高まりました。'),
        (r'低下した。', '低下しました。'),
        (r'上回った。', '上回りました。'),
        (r'下回った。', '下回りました。'),
        (r'見られた。', '見られました。'),
        (r'(?<!り)なった。', 'なりました。'),
    ]
    for pat, rep in replacements:
        result = re.sub(pat, rep, result)

    return result


def _rule_based_fix(content: str) -> str:
    """LLM不要のルールベース修正（タイトル正規化・免責事項補完）。
    _normalize_style()が対応しない 【】形式タイトルと免責事項の自動補完を行う。
    """
    lines = content.split('\n')

    if lines:
        first = lines[0].strip()
        # 【記事タイトル】XXX → # XXX
        m = re.match(r'^【(?:記事タイトル|タイトル)】\s*(.+)', first)
        if m:
            lines[0] = f"# {m.group(1).strip()}"
        else:
            # **記事タイトル:** XXX → # XXX（_normalize_styleの補完）
            m2 = re.match(r'^\*{0,2}(?:記事タイトル|タイトル)[：:]\s*\*{0,2}\s*(.+)', first)
            if m2:
                lines[0] = f"# {m2.group(1).strip('* ').strip()}"

        # 先頭が # で始まらない場合、本文中の最初の # 行を先頭に移動
        if lines and not lines[0].startswith('# '):
            for i, line in enumerate(lines[1:], 1):
                if line.startswith('# '):
                    lines = [lines[i]] + lines[:i] + lines[i + 1:]
                    break

    content = '\n'.join(lines)

    # 免責事項の補完（見出し「免責事項」が必須）
    _disclaimer = (
        "※本記事は情報提供を目的としており、"
        "投資の推奨・勧誘を行うものではありません。"
        "投資に関する最終判断はご自身の責任でお願いいたします。"
    )
    if "免責事項" not in content:
        if _disclaimer[:10] in content:
            # 免責文章はあるが見出しがない → 見出しを前に挿入
            content = content.replace(
                _disclaimer[:10],
                f"## 免責事項\n\n{_disclaimer[:10]}",
                1,
            )
        else:
            # 免責事項が全くない → 末尾に追加
            content += f"\n\n## 免責事項\n\n{_disclaimer}"

    return content.strip()


_SPECULATIVE_PATTERNS = [
    (r'業績の改善が期待される企業や、特定の要因が背景にある銘柄も見られ', '一部銘柄では個別の値動きが見られ'),
    (r'業績の改善が期待される企業が目立ちました', '個別に値上がりした銘柄も見られました'),
    (r'可能性が背景にあるとされています', '背景は未公表です'),
    (r'市場の需要が拡大している可能性が背景にあるとされています', '背景は未公表です'),
    (r'それぞれの業界における具体的な要因が影響している可能性があります', '背景は未公表です'),
    (r'明確な情報が公表されていません', '背景は未公表です'),
]


def _remove_speculative_expressions(content: str) -> str:
    """ランキング外の本文に残る推測表現をニュートラルな表現に置換する。"""
    for pattern, replacement in _SPECULATIVE_PATTERNS:
        content = re.sub(pattern, replacement, content)
    return content


# 後処理（_normalize_style）で解決できる問題キーワード — LLM修正不要
_LOCAL_FIX_SKIP_KEYWORDS = [
    "背景は未公表", "文体", "ですます", "寄与しました",
    "確認されました", "詳細は未公表", "普通体",
]


def _local_fix(content: str, issues: list, finance_data: dict) -> str:
    """
    全文再生成せず、指摘箇所のみを修正する（Level 2修正）。

    - まず後処理（_normalize_style）で解決を試みる
    - 残った問題のみLLMによる局所修正を行う
    - LLM出力が短すぎる場合は元の内容を保持
    """
    if not issues:
        return content

    # Step0: 数値乖離は直接置換で修正（LLM不要・確実）
    # 円建て: "記事=167.4円 / 実際=158.44円"
    # pt建て: "記事=25.3pt / 実際=18.50pt"
    # ドル建て: "記事=80.5ドル / 実際=65.20ドル"
    _UNIT_PATTERNS = [
        (r'記事=(\d+\.?\d*)円 / 実際=(\d+\.?\d*)円',   "円"),
        (r'記事=(\d+\.?\d*)pt / 実際=(\d+\.?\d*)pt',   "pt"),
        (r'記事=(\d+\.?\d*)ドル / 実際=(\d+\.?\d*)ドル', "ドル"),
    ]
    for issue in issues:
        for unit_pattern, unit in _UNIT_PATTERNS:
            m = re.search(unit_pattern, issue)
            if m:
                wrong_val   = m.group(1)
                correct_raw = float(m.group(2))
                correct_val = f"{correct_raw:.2f}"
                for wrong_pat in [f"{wrong_val}{unit}", wrong_val]:
                    if wrong_pat in content:
                        content = content.replace(wrong_pat, f"{correct_val}{unit}")
                        print(f"  🔢 数値直接修正: {wrong_pat} → {correct_val}{unit}")
                break  # 単位がマッチしたら次のissueへ

    # Step1: 後処理で解決できるものを適用
    content = _normalize_style(content)

    # Step2: 後処理で解決できない問題を抽出
    llm_fix_needed = [
        issue for issue in issues
        if not any(skip in issue for skip in _LOCAL_FIX_SKIP_KEYWORDS)
    ]
    if not llm_fix_needed:
        return content  # 後処理だけで解決済み

    # Step3: LLMによる局所修正（ask_financeを使用・短タイムアウト）
    from llm import ask_finance as _ask_fix
    issues_text = "\n".join(f"- {i}" for i in llm_fix_needed)
    fix_prompt = (
        "以下の記事の特定箇所のみを修正してください。\n"
        "記事全体を書き直す必要はありません。\n\n"
        f"【修正が必要な箇所】\n{issues_text}\n\n"
        "【修正ルール】\n"
        "- 指摘された箇所のみを最小限修正する\n"
        "- 他の部分は一切変更しない\n"
        "- ですます体を維持する\n\n"
        f"【記事】\n{content}\n\n"
        "修正後の記事全文を出力してください:"
    )
    try:
        fixed = _ask_fix(fix_prompt)
        if fixed and len(fixed) > len(content) * 0.5:
            return _normalize_style(fixed)
    except Exception as e:
        print(f"  ⚠️ 局所修正失敗（元の記事を使用）: {e}")

    return content


def _final_clean(content: str, topic: str, genre_id: str) -> str:
    """
    スコアに関わらず必ず適用する最終クリーニング。
    中国語・韓国語・誤字を修正してから返す。
    """
    from llm import ask_plain as _ask_plain

    # Step1: 機械的な除去
    content = _remove_chinese_chars(content)

    # Step2: 残存する問題をチェック
    issues = []
    chinese_typos = re.findall(
        r'[們样]|什么|什麼|為什|为什|这个|那个|[样]的',
        content
    )
    if chinese_typos:
        issues.append(f"中国語誤字: {chinese_typos[:3]}")
    korean = re.findall(r'[\uac00-\ud7af]{2,}', content)
    if korean:
        issues.append(f"韓国語残存: {''.join(korean[:3])}")

    if not issues:
        return content

    # Step3: LLMで修正
    print(f"  🔧 最終修正中（{', '.join(issues)}）...")
    fix_prompt = (
        "以下の記事に問題があります。修正してください。\n"
        f"【問題】\n" + "\n".join(issues) + "\n"
        "【修正ルール】\n"
        "- 中国語・韓国語の文字を削除する\n"
        "- 「們」→「たち」または削除\n"
        "- 「什么」「什麼」「样的」→削除\n"
        "- 「这个」「那个」→削除\n"
        "- 日本語として不自然な表現を自然な日本語に修正\n"
        "- 記事の内容・構成は変えない\n"
        "- 修正した記事全体をそのまま出力する\n"
        f"【記事】\n{content}"
    )
    fixed = _ask_plain(fix_prompt)
    if fixed and len(fixed) > len(content) * 0.5:
        fixed = _remove_chinese_chars(fixed)
        print("  ✅ 最終修正完了")
        return fixed
    return content


# --- MONETIZATION FOOTER START ---
_FOOTER_TEMPLATE = """
---
## 🛠️ この記事で紹介した環境・ツール
| ツール | 用途 | 入手先 |
|--------|------|--------|
| Python | プログラミング言語 | python.org |
| VS Code | コードエディタ | code.visualstudio.com |
| Ollama | ローカルLLM実行 | ollama.ai |

## 📚 関連記事
- Pythonで始めるAI開発
- ローカルLLMの活用法
- 自動化スクリプトの作り方

---
*この記事はAIエージェントによって自動生成されました。*
*誤りや改善点があればコメントでお知らせください。*
"""


def _add_footer(content: str, topic: str) -> str:
    """記事末尾に収益導線フッターを追加する"""
    if "この記事で紹介した環境" in content:
        return content  # 既にフッターがある場合はスキップ
    return content + _FOOTER_TEMPLATE
# --- MONETIZATION FOOTER END ---


# --- TOPIC KNOWLEDGE START ---
def _get_topic_knowledge(topic: str) -> str:
    """
    トピックに応じた正確な技術知識を返す。
    RAGが取得できない場合の補完として使用する。
    """
    topic_lower = topic.lower()
    if "ollama" in topic_lower:
        return """
【Ollamaの正確な使い方】
- Ollamaはapi_keyが不要。ローカルで動作する。
- Pythonからの呼び出し例:
  import requests
  response = requests.post('http://localhost:11434/api/generate',
      json={"model": "qwen2.5-coder:7b", "prompt": "Hello", "stream": False})
  print(response.json()["response"])
- または公式ライブラリ:
  import ollama
  response = ollama.generate(model='llama2', prompt='Hello')
  print(response['response'])
- モデル一覧取得: ollama.list()
- チャット形式: ollama.chat(model='llama2', messages=[...])
"""
    if "fastapi" in topic_lower or "flask" in topic_lower:
        return """
【WebフレームワークAPIの正確な使い方】
- Flask: from flask import Flask, jsonify; app = Flask(__name__)
- FastAPI: from fastapi import FastAPI; app = FastAPI()
- どちらもapi_keyは不要（ローカル開発時）
"""
    return ""
# --- TOPIC KNOWLEDGE END ---


def generate_article(
    topic: str,
    genre_id: str = "python_tips",
    extra_context: str = "",
    max_retries: int = 3,
    variant: str = "hatena",
    finance_cache: dict = None,
    extra_prompt: str = "",
    force_overwrite: bool = False,
) -> dict:
    """
    RAGを使って技術記事を生成する。
    Args:
        topic:          記事のトピック
        genre_id:       ジャンルID
        extra_context:  追加コンテキスト
        max_retries:    生成リトライ上限（デフォルト3）
        variant:        "zenn"（概要版）or "hatena"（詳細版）
        finance_cache:  投資データキャッシュ（collect_finance_data()の結果）
        extra_prompt:   プロンプト末尾に追加するテキスト（整合性修正用の正値指示等）
    Returns:
        {"title", "content", "path", "rag_hits", "word_count"}
    """
    if variant == "zenn":
        print(f"\n  📝 記事生成（Zenn概要版）: {topic}")
    else:
        print(f"\n  📝 記事生成（はてな詳細版）: {topic}")

    # --- DEDUP CHECK START ---
    try:
        from content_checker import check_topic_saturation
        saturated, sat_reason = check_topic_saturation(genre_id, topic)
        if saturated:
            print(f"  ⚠️ {sat_reason} → スキップ")
            return {"error": f"トピック飽和: {sat_reason}"}
    except Exception as e:
        print(f"  ⚠️ 重複チェックスキップ: {e}")
    # --- DEDUP CHECK END ---

    # RAGで関連情報を取得（投資記事はリアルタイムデータ優先のためスキップ）
    rag_context = ""
    rag_hits    = 0
    if genre_id == "finance_news":
        print(f"  ℹ️ 投資記事はRAGスキップ（リアルタイムデータ優先）")
    else:
        try:
            from rag_retriever import search, format_context
            results     = search(topic, top_k=4)
            rag_context = format_context(results, max_chars=2000)
            rag_hits    = len(results)
            if rag_context:
                # 無関係コードの混入チェック
                noise_patterns = [
                    "return jsonify", "app.route", "@app.",
                    "JWT", "client.generate(text=", "{'error':",
                ]
                if any(p in rag_context for p in noise_patterns):
                    print(f"  ⚠️ RAGコンテキストに無関係コード混入 → スキップ")
                    rag_context = ""
                    rag_hits    = 0
                else:
                    print(f"  📚 RAG: {rag_hits}件の関連知識を注入")
        except Exception as e:
            print(f"  ⚠️ RAGスキップ: {e}")

    # 投資ジャンルの場合: リアルタイムデータをコンテキストに注入（圧縮版）
    _finance_data_for_check = None  # ファクトチェック用に保持
    _fc_result              = None  # ファクトチェック結果（ループ外で保持・result定義後に代入）
    if genre_id == "finance_news" and not extra_context:
        try:
            from finance_data_collector import collect_finance_data, compress_finance_context
            if finance_cache is not None:
                print(f"  📊 キャッシュデータを使用（データ収集をスキップ）")
                _data = finance_cache
            else:
                _data = collect_finance_data()
            extra_context = compress_finance_context(_data)
            _finance_data_for_check = _data
        except Exception as e:
            print(f"  ⚠️ 投資データ取得失敗: {e}")

    # コンテキストを合成
    context = ""
    # トピック固有知識を注入（RAGより優先して先頭に配置）
    topic_knowledge = _get_topic_knowledge(topic)
    if topic_knowledge:
        context += topic_knowledge + "\n\n"
        print(f"  📖 トピック知識を注入: {topic[:30]}")
    if rag_context:
        context += f"【最新情報・公式ドキュメント】\n{rag_context}\n\n"
    if extra_context:
        context += f"【追加情報】\n{extra_context}\n"
    if not context:
        context = "（関連情報なし：一般的な知識で補完してください）"

    # テンプレート選択（variant・ジャンルに応じて切り替え）
    genre      = next((g for g in TECH_GENRES if g["id"] == genre_id), TECH_GENRES[0])
    is_finance = genre_id == "finance_news"

    # 品質スコア設定
    # 投資記事: 合格9点・最終試行での許容下限8点・3回固定
    # その他:   合格7点・許容下限7点（変更なし）
    if is_finance:
        PASS_SCORE   = 9  # 合格基準（9点以上で即保存）
        ACCEPT_SCORE = 8  # 最終試行での保存許容スコア
        max_retries  = 3
    else:
        PASS_SCORE   = 7
        ACCEPT_SCORE = 7
        max_retries  = max_retries
    if is_finance:
        if variant == "zenn":
            template   = ZENN_FINANCE_TEMPLATE
            min_length = 1200  # Zenn版は概要版（1200〜1800文字目標）
        else:
            template   = HATENA_FINANCE_TEMPLATE
            min_length = 2000  # Ollama出力量に合わせて調整（4000 → 2000）
        today_str = datetime.now().strftime('%Y年%m月%d日')
        template  = template.replace(
            "以下の市場データを使って",
            f"本日（{today_str}）の市場データを使って"
        )
        prompt = template.format(topic=topic, context=context[:12000])
    elif variant == "zenn":
        template   = ZENN_TEMPLATE
        min_length = 1000
        prompt = _QUALITY_RULES + template.format(topic=topic, context=context[:6000])
    else:
        template   = HATENA_TEMPLATE
        min_length = 2000
        prompt = _QUALITY_RULES + template.format(topic=topic, context=context[:6000])

    # 整合性修正用の正値指示をプロンプト末尾に追加
    if extra_prompt:
        prompt += extra_prompt

    # 学習済みルールをプロンプト先頭に注入（自己改善ループの蓄積結果を活用）
    from prompt_improver import (
        load_rules as _pi_load_rules,
        get_prompt_prefix as _pi_get_prefix,
        analyze_failure as _pi_analyze,
        apply_fix as _pi_apply_fix,
        record_failure as _pi_record,
        record_success as _pi_record_success,
        save_rules as _pi_save,
    )
    _pi_rules = _pi_load_rules()
    _pi_prefix = _pi_get_prefix(_pi_rules)
    if _pi_prefix:
        prompt = _pi_prefix + "\n\n" + prompt

    # 記事生成（品質チェック + レビュー付きリトライあり）
    from llm import ask_plain
    content = ""
    review_score    = 0
    review_passed   = True
    review_feedback = "レビューなし"
    for attempt in range(max_retries):
        if is_finance:
            from llm import ask_finance as _gen
            _model_label = "qwen3:14b・投資記事専用"
        else:
            from llm import ask_plain as _gen
            from llm import PLANNER_MODEL as _PM
            _model_label = _PM
        print(f"  🧠 生成中 ({_model_label})"
              f"{' 再試行 ' + str(attempt) if attempt > 0 else ''}...")
        # finance/tech 共通: 3000文字以上必要なためmax_tokens=6000
        content = _gen(prompt, max_tokens=6000)
        # 中国語文字を除去（置換リストで対応済みの文字を日本語化）
        content = _remove_chinese_chars(content)
        # finance記事: 品質チェック前に文体・表現を正規化
        if is_finance and content:
            content = _normalize_stock_expressions(content)
            content = _normalize_style(content)
        passed, reason = _quality_check_v2(content, min_chars=min_length,
                                           require_code=not is_finance, genre_id=genre_id)
        if not passed:
            if attempt < max_retries - 1:
                print(f"  ⚠️ 品質不足: {reason} → リトライ {attempt + 1}/{max_retries - 1}")
                # 自己改善: 失敗原因を分析してプロンプトを修正
                _analysis = _pi_analyze(content, [reason])
                print(f"  🔍 原因分析: {_analysis['cause']}")
                print(f"  💡 仮説: {_analysis['hypothesis']}")
                if _analysis["fix"]:
                    _pi_record(_pi_rules, reason, _analysis["fix"], category=_analysis.get("category", "unknown"))
                    _pi_save(_pi_rules)
                    prompt = _pi_apply_fix(prompt, _analysis["fix"])
                    print(f"  🔧 プロンプト自動修正: {_analysis['fix'][:60]}...")
                else:
                    # フォールバック: ジャンル固定のリトライ指示
                    if is_finance:
                        _fallback_req = (
                            "必須セクション（市場概況・まとめ・免責事項）を含めてください。"
                            "日経平均の数値を必ず記載してください。"
                        )
                    else:
                        _fallback_req = (
                            f"必ず{min_length}文字以上・見出し(##)3個以上"
                            "・コード例(```python)1個以上・まとめセクションを含めてください。"
                        )
                    prompt = (
                        prompt
                        + f"\n\n【重要・再試行{attempt + 1}回目】\n"
                        + f"前回の出力が品質基準を満たしませんでした。理由: {reason}\n"
                        + _fallback_req
                        + "\n必ず日本語で書いてください。中国語（简体字）は絶対に使わないこと。"
                    )
                continue
            else:
                if is_finance:
                    # finance記事: 再生成せずqwen3:14bで局所修正を試みる
                    # ただし「内容が極端に少ない」場合は局所修正で解決できないためスキップ
                    if "極端に少ない" in reason or "内容が少ない" in reason:
                        print(f"  ⚠️ コンテンツ不足({reason}) → 局所修正不可・保存続行")
                    else:
                        print(f"  🔧 品質未達({reason}) → qwen3:14bで局所修正中...")
                        _fixed = _local_fix(content, [reason], _finance_data_for_check or {})
                        # 修正後に短くなっていたら元を使う
                        if len(_fixed) >= len(content):
                            content = _fixed
                        # 局所修正後に免責事項・タイトルが失われることがあるため再適用
                        if is_finance:
                            content = _rule_based_fix(content)
                        _passed2, _reason2 = _quality_check_v2(
                            content, min_chars=min_length,
                            require_code=not is_finance, genre_id=genre_id
                        )
                        if _passed2:
                            print(f"  ✅ 局所修正で品質基準クリア")
                        else:
                            print(f"  ⚠️ 局所修正後も未達({_reason2}) → 下書きとして保存続行")
                else:
                    print(f"  ❌ 品質基準未達: {reason}")
                    return {"error": f"品質基準未達: {reason}"}

        # --- QUALITY REVIEW START ---
        from article_reviewer import review_article
        review = review_article(content, topic, genre_id=genre_id)
        print(f"  📊 品質スコア: {review['score']}/10 "
              f"({'✅ pass' if review['passed'] else '❌ fail'})")
        if review["issues"]:
            print(f"  ⚠️ 問題点: {', '.join(review['issues'][:3])}")
        review_score    = review["score"]
        review_passed   = review["passed"]
        review_feedback = review["feedback"]
        is_last_attempt = (attempt == max_retries - 1)
        if review_score < PASS_SCORE:
            if not is_last_attempt:
                # Level 2: 局所修正で解決できるか試みる（全文再生成の前に）
                review_issues = review.get("issues", [])
                if is_finance and review_issues:
                    print(f"  🔧 局所修正を試行中（score={review_score}）...")
                    fixed = _local_fix(content, review_issues,
                                       _finance_data_for_check or {})
                    from article_reviewer import review_article as _re_review
                    re_result = _re_review(fixed, topic, genre_id=genre_id)
                    if re_result["score"] >= PASS_SCORE:
                        print(f"  ✅ 局所修正で解決"
                              f"（score {review_score}→{re_result['score']}）")
                        content       = fixed
                        review_score  = re_result["score"]
                        review_passed = re_result["passed"]
                        review_feedback = re_result["feedback"]
                        # レビュー通過 → ファクトチェックへ進む（continueしない）
                    else:
                        # Level 3: 局所修正では解決できず → 全文再生成
                        issues_text = "\n".join(review_issues)
                        if issues_text:
                            prompt += (
                                f"\n\n【前回の品質指摘（必ず修正すること）】\n"
                                f"{issues_text}\n"
                                "上記の問題を修正して、より高品質な記事を書き直してください。"
                            )
                        print(f"  🔄 全文再生成（局所修正でも score={re_result['score']}"
                              f" < {PASS_SCORE}）→ attempt {attempt + 1}/{max_retries}")
                        continue
                else:
                    # 非finance or 指摘なし: 従来通り全文再生成
                    issues_text = "\n".join(review_issues)
                    if issues_text:
                        prompt += (
                            f"\n\n【前回の品質指摘（必ず修正すること）】\n"
                            f"{issues_text}\n"
                            "上記の問題を修正して、より高品質な記事を書き直してください。"
                        )
                    print(f"  ⚠️ 品質不足（score={review_score} < {PASS_SCORE}）"
                          f"→ 再生成 {attempt + 1}/{max_retries}")
                    continue
            else:
                # 最終試行
                if review_score >= ACCEPT_SCORE:
                    print(f"  ⚠️ 最終試行: score={review_score}"
                          f"（目標{PASS_SCORE}未達だが{ACCEPT_SCORE}以上のため保存）")
                else:
                    print(f"  ❌ 品質基準未達（最終試行）: score={review_score} < {ACCEPT_SCORE}")
                    return {
                        "path":   None,
                        "score":  review_score,
                        "passed": False,
                        "reason": f"品質基準未達: {review_score}/{ACCEPT_SCORE}",
                    }
        # --- QUALITY REVIEW END ---

        # --- FACT CHECK START ---
        if is_finance and _finance_data_for_check:
            try:
                from fact_checker import fact_check
                fc_result = fact_check(content, _finance_data_for_check, variant=variant)
                # warningsのみの場合は再生成不要（軽微な表現の指摘）
                # issuesがある場合のみ修正・再生成を試みる
                if fc_result["warnings"]:
                    for w in fc_result["warnings"]:
                        print(f"  ⚠️ ファクトチェック警告: {w}")
                if not fc_result["passed"]:
                    # issues（重大問題）がある場合のみ修正・再生成
                    fc_issues   = fc_result["issues"]
                    issues_text = "\n".join(f"- {i}" for i in fc_issues)
                    if attempt < max_retries - 1:
                        # Level 2: 局所修正で解決できるか試みる
                        print(f"  🔧 ファクトチェック失敗 → 局所修正を試行中...")
                        fixed_fc = _local_fix(content, fc_issues,
                                              _finance_data_for_check or {})
                        from fact_checker import fact_check as _re_fc
                        fc_re = _re_fc(fixed_fc, _finance_data_for_check,
                                       variant=variant)
                        if fc_re["passed"]:
                            print(f"  ✅ 局所修正でファクトチェック解決（再生成不要）")
                            content = fixed_fc
                            _fc_result = fc_re
                            # continueせず次のチェックへ
                        else:
                            # Level 3: 全文再生成
                            print(f"  ❌ ファクトチェック失敗 → 修正指示付きで再生成")
                            prompt += (
                                f"\n\n【ファクトチェック指摘事項 - 必ず修正すること】\n"
                                f"{issues_text}\n"
                                "上記の問題を修正してください。特に:\n"
                                "- 「と考えられます」→「背景は未公表」に変更\n"
                                "- 曖昧表現を削除して事実のみを記載\n"
                            )
                            continue  # 再生成
                    else:
                        # 最終試行は保存続行
                        print(f"  ⚠️ ファクトチェック失敗（最終試行のため保存続行）")
                        _fc_result = fc_result
                else:
                    print(f"  ✅ ファクトチェック: 問題なし")
                    _fc_result = fc_result
            except Exception as e:
                print(f"  ⚠️ ファクトチェックスキップ: {e}")
        # --- FACT CHECK END ---

        # --- DYNAMIC VERIFICATION START ---
        if is_finance and _finance_data_for_check:
            try:
                from dynamic_verifier import verify_article_time_expressions
                verify_result = verify_article_time_expressions(
                    content, _finance_data_for_check
                )

                if verify_result["has_issues"]:
                    if attempt < max_retries - 1:
                        print(f"  ❌ 時間表現の検証失敗 → 修正指示付きで再生成")
                        prompt += verify_result["correction_prompt"]
                        continue
                    else:
                        print(f"  ⚠️ 時間表現の検証警告（最終試行のため保存続行）")

                elif verify_result["verified"]:
                    print(f"  ✅ 時間表現の検証完了: {len(verify_result['verified'])}件")

            except Exception as e:
                print(f"  ⚠️ 時間表現検証スキップ: {e}")
        # --- DYNAMIC VERIFICATION END ---

        break

    # フッターを追加（投資記事は技術ツール紹介フッターをスキップ）
    if not is_finance:
        content = _add_footer(content, topic)

    # 導線文を注入（Zenn→はてな誘導 / はてな→Zenn逆リンク）
    # finance_news はZenn停止中のためupsellをスキップ
    try:
        if not is_finance:
            from upsell_generator import inject_upsell_into_article
            content = inject_upsell_into_article(
                content=content,
                topic=topic,
                genre_id=genre_id,
                variant=variant,
                hatena_url="",   # publisher_linker.py が後で更新
                zenn_url="",
            )
    except Exception as e:
        print(f"  ⚠️ 導線文注入スキップ: {e}")

    # 日経平均数値の整合チェック（投資記事のみ）
    if is_finance and _finance_data_for_check:
        try:
            nikkei_str = _finance_data_for_check.get("market_summary", {}).get("nikkei_price", "")
            nikkei_val = float(nikkei_str.replace(',', '')) if nikkei_str else 0.0
            if nikkei_val > 0:
                content = _check_nikkei_consistency(content, nikkei_val)
        except Exception as e:
            print(f"  ⚠️ 日経数値整合チェックスキップ: {e}")

    # SEOタイトル自動生成・整合チェック（投資記事のみ）
    if is_finance and _finance_data_for_check:
        try:
            seo_title = _make_seo_title(topic, _finance_data_for_check)
            lines = content.split('\n')
            if lines and lines[0].startswith('# '):
                lines[0] = f"# {seo_title}"
                content   = '\n'.join(lines)
                print(f"  🏷️ SEOタイトル: {seo_title}")
            # 整合チェック
            consistency_warns = _check_title_content_consistency(
                seo_title, content, _finance_data_for_check
            )
            for w in consistency_warns:
                print(f"  ⚠️ タイトル整合: {w}")
        except Exception as e:
            print(f"  ⚠️ SEOタイトル生成スキップ: {e}")

    # グラフ生成・埋め込み（はてな版・投資記事のみ）
    if is_finance and variant == "hatena" and _finance_data_for_check:
        try:
            from chart_generator import generate_all_charts
            from hatena_publisher import get_chart_github_url
            charts = generate_all_charts(_finance_data_for_check)
            if charts:
                LABELS = {
                    "up_chart":    "値上がり率ランキング TOP5",
                    "down_chart":  "値下がり率ランキング TOP5",
                    "macro_chart": "主要指標 変動率比較",
                }
                chart_section = "\n\n## 📊 本日の市場データ（グラフ）\n\n"
                for key, img_path in charts.items():
                    label   = LABELS.get(key, key)
                    img_url = get_chart_github_url(img_path)
                    chart_section += f"### {label}\n"
                    chart_section += (
                        f'<figure><img src="{img_url}" alt="{label}"'
                        f' style="max-width:100%;" /></figure>\n\n'
                    )
                # "## まとめ" の直前に挿入（バリエーション対応）
                _m = re.search(r'^(##\s+.*まとめ.*)', content, re.MULTILINE)
                if _m:
                    content = content.replace(_m.group(1), chart_section + _m.group(1), 1)
                else:
                    content += chart_section
                print(f"  📊 チャートセクション埋め込み完了（{len(charts)}枚）")
        except Exception as e:
            print(f"  ⚠️ グラフ生成スキップ: {e}")

    # アフィリエイトフッターを追加（投資記事・はてな版のみ）
    if is_finance and variant == "hatena":
        _affiliate = _build_affiliate_footer()
        if _affiliate and "## 免責事項" in content:
            content = content.replace("## 免責事項", _affiliate + "\n\n## 免責事項", 1)

    # 保存前の最終クリーニング（スコアに関わらず必ず実行）
    content = _final_clean(content, topic, genre_id)

    # 表現正規化（投資記事のみ）
    if genre_id == "finance_news":
        content = _normalize_stock_expressions(content)
        content = _remove_speculative_expressions(content)
        content = _normalize_style(content)

    # 最終品質確認（中国語・韓国語が残っていないか）
    remaining_chinese = re.findall(
        r'[們样]|什么|什麼|為什|为什|这个|那个|[样]的',
        content
    )
    remaining_korean  = re.findall(r'[\uac00-\ud7af]{2,}', content)
    if remaining_chinese or remaining_korean:
        print(f"  ⚠️ 修正後も問題残存: chinese={remaining_chinese[:2]} korean={remaining_korean[:2]}")
        if review_score >= 7:
            review_score  = 6
            review_passed = False
            print(f"  ⬇️ スコア強制降格: {review_score}/10（異常文字残存）")

    # ファイル保存（スコアをメタデータとして末尾に付加）
    path = _save_article(topic, content, variant=variant, genre_id=genre_id, score=review_score)

    # --- DEDUP REGISTER START ---
    if force_overwrite:
        # 整合性修正再生成：重複チェックをスキップしてDB登録のみ行う
        try:
            from content_checker import check_duplicate as _cd
            _cd(title=topic, content=content, out_path=path,
                score=review_score, variant=variant)
        except Exception as e:
            print(f"  ⚠️ 重複DB更新スキップ: {e}")
    else:
        try:
            from content_checker import check_duplicate
            dup_result = check_duplicate(
                title=topic,
                content=content,
                out_path=path,
                score=review_score,
                variant=variant,
            )
            if dup_result["duplicate"]:
                reason = dup_result.get("reason", "")
                print(f"  ⏭️ 既存記事の方が高品質のためスキップ: {reason}")
                path.unlink(missing_ok=True)
                # 品質は十分だが既存記事が上位のためスキップ → 成功扱い（再起動不要）
                return {
                    "path":   None,
                    "score":  review_score,
                    "passed": True,
                    "reason": f"品質比較スキップ（既存記事保持）: {reason}",
                }
        except Exception as e:
            print(f"  ⚠️ 重複登録スキップ: {e}")
    # --- DEDUP REGISTER END ---

    # 成功パターンを記録（自己改善ループ）
    try:
        _pi_record_success(_pi_rules, content, review_score)
        _pi_save(_pi_rules)
    except Exception:
        pass

    # 有料記事適性チェック・フッター注入（はてな版のみ）
    paid_suitable = False
    paid_label    = "📝 無料記事"
    try:
        from paid_content_generator import (
            is_suitable_for_paid,
            generate_paid_label,
            generate_paid_footer,
        )
        if variant == "hatena":
            paid_suitable = is_suitable_for_paid(content, review_score, genre_id)
            paid_label    = generate_paid_label(genre_id, review_score)
            if paid_suitable:
                print(f"  💎 有料記事適性: {paid_label}")
                paid_footer = generate_paid_footer(genre_id)
                if paid_footer:
                    content = content.rstrip() + "\n" + paid_footer
                    # フッター追加後にファイルを上書き保存
                    path.write_text(content, encoding="utf-8")
    except Exception as e:
        print(f"  ⚠️ 有料判定スキップ: {e}")

    # メタデータ記録
    result = {
        "title":           topic,
        "genre":           genre_id,
        "content":         content,
        "path":            str(path),
        "rag_hits":        rag_hits,
        "word_count":      len(content),
        "generated_at":    datetime.now().isoformat(),
        "review_score":    review_score,
        "review_passed":   review_passed,
        "review_feedback": review_feedback,
        "paid_suitable":   paid_suitable,
        "paid_label":      paid_label,
    }
    # ファクトチェック結果をループ外から代入（ループ内では result 未定義のため）
    if _fc_result is not None:
        result["fact_check"] = _fc_result
    _log_performance(result)
    print(f"  ✅ 生成完了: {path.name} ({len(content)}文字)")

    # Qdrantクライアントの明示的クローズ（終了時 __del__ エラー抑制）
    try:
        import rag_retriever
        if rag_retriever._qdrant_client is not None:
            rag_retriever._qdrant_client.close()
            rag_retriever._qdrant_client = None  # __del__ 二重呼び出し防止
    except Exception:
        pass

    return result


def _save_draft(
    content: str,
    genre_id: str,
    topic: str,
    variant: str = "hatena",
) -> Path:
    """品質チェック前に下書きをファイルに保存する。
    content/finance/drafts/ 以下に保存し、最終版とは別管理する。
    """
    draft_dir = get_content_dir(genre_id).parent / "drafts"
    draft_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug     = re.sub(r"[^\w\s-]", "", topic.lower())
    slug     = re.sub(r"\s+", "_", slug.strip())[:30] or "draft"
    suffix   = "_zenn" if variant == "zenn" else "_hatena"
    path     = draft_dir / f"{date_str}_{slug}{suffix}_draft.md"
    path.write_text(content, encoding="utf-8")
    return path


def _save_article(
    topic: str,
    content: str,
    variant: str = "hatena",
    genre_id: str = "",
    score: int = 0,
) -> Path:
    """記事をジャンル別サブディレクトリに保存する。
    スコアをHTMLコメントとして末尾に付加する（重複比較で使用）。
    """
    save_dir = get_content_dir(genre_id) if genre_id else CONTENT_DIR
    save_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    slug     = re.sub(r"[^\w\s-]", "", topic.lower())
    slug     = re.sub(r"\s+", "_", slug.strip())[:40] or "article"
    suffix   = "_zenn" if variant == "zenn" else "_hatena"
    filename = f"{date_str}_{slug}{suffix}.md"
    path     = save_dir / filename
    counter  = 1
    while path.exists():
        path    = save_dir / f"{date_str}_{slug}{suffix}_{counter}.md"
        counter += 1
    meta = (
        f"\n<!-- score:{score} variant:{variant}"
        f" generated:{datetime.now().strftime('%Y-%m-%d %H:%M')} -->"
    )
    path.write_text(content + meta, encoding="utf-8")
    return path


def _log_performance(result: dict):
    """生成ログを記録する"""
    PERF_LOG.parent.mkdir(exist_ok=True)
    logs = []
    if PERF_LOG.exists():
        try:
            logs = json.loads(PERF_LOG.read_text(encoding="utf-8"))
        except Exception:
            pass
    log_entry = {k: v for k, v in result.items() if k != "content"}
    # 品質チェック結果を追加
    passed, reason = _quality_check(result.get("content", ""))
    log_entry["quality_passed"] = passed
    log_entry["quality_reason"] = reason
    logs.append(log_entry)
    logs = logs[-500:]
    PERF_LOG.write_text(
        json.dumps(logs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def show_content_stats() -> str:
    """生成コンテンツの統計を表示する"""
    if not PERF_LOG.exists():
        return "生成記事なし"
    logs  = json.loads(PERF_LOG.read_text(encoding="utf-8"))
    files = list(CONTENT_DIR.rglob("*.md")) if CONTENT_DIR.exists() else []
    lines = [
        f"## 📝 コンテンツ統計",
        f"生成記事数: {len(files)}件",
        f"総生成数:   {len(logs)}件",
    ]
    if logs:
        avg_words    = sum(l.get("word_count", 0) for l in logs) / len(logs)
        avg_rag      = sum(l.get("rag_hits",   0) for l in logs) / len(logs)
        quality_pass = sum(1 for l in logs if l.get("quality_passed", True))
        lines.append(f"平均文字数: {avg_words:.0f}文字")
        lines.append(f"平均RAGヒット: {avg_rag:.1f}件")
        lines.append(f"品質通過率: {quality_pass}/{len(logs)} ({quality_pass / len(logs) * 100:.0f}%)")
        scores = [l.get("review_score", 0) for l in logs if l.get("review_score")]
        if scores:
            avg_score  = sum(scores) / len(scores)
            fail_count = sum(1 for l in logs if not l.get("review_passed", True))
            lines.append(f"平均品質スコア: {avg_score:.1f}/10")
            lines.append(f"fail率: {fail_count}/{len(logs)} ({fail_count / len(logs) * 100:.0f}%)")
        # 有料適性統計
        paid_count = sum(1 for l in logs if l.get("paid_suitable", False))
        if paid_count > 0:
            lines.append(f"有料適性記事: {paid_count}件 / {len(logs)}件 ({paid_count / len(logs) * 100:.0f}%)")
        lines.append("")
        lines.append("### 最新5件")
        for log in reversed(logs[-5:]):
            paid_mark = " 💎" if log.get("paid_suitable") else ""
            lines.append(
                f"- {log.get('generated_at','')[:10]} "
                f"{log.get('title','')[:40]} "
                f"({log.get('word_count',0)}文字){paid_mark}"
            )
    return "\n".join(lines)

"""
獲得スキルの品質評価・改善システム。
評価項目:
1. 静的解析（code_checker.py）
2. LLMによる品質レビュー（check_and_fix 内で実行）
3. 問題があれば自動修正してファイルに書き戻す
"""
import json
import sys
from pathlib import Path
from datetime import datetime

AGENT_ROOT  = Path(__file__).parent
SKILL_DB    = AGENT_ROOT / "memory" / "skill_db.json"
EVOLVED_DIR = AGENT_ROOT / "tools" / "evolved"
EVAL_LOG    = AGENT_ROOT / "knowledge" / "skill_eval_log.md"


def _collect_targets() -> list[dict]:
    """
    評価対象ファイルを収集する。
    1. tools/evolved/*.py（自動獲得ツール）
    2. skill_db に登録されているが evolved にないスキル（not_found として記録）
    Returns: [{"name": str, "path": Path | None, "source": str}]
    """
    targets = []
    seen_names = set()

    # 1. EVOLVED_DIR のファイルを全て対象とする
    if EVOLVED_DIR.exists():
        for filepath in sorted(EVOLVED_DIR.glob("*.py")):
            if filepath.name.startswith("_") or filepath.name.startswith("."):
                continue
            name = filepath.stem
            targets.append({"name": name, "path": filepath, "source": "evolved"})
            seen_names.add(name)

    # 2. skill_db のエントリのうち evolved に対応ファイルがないもの
    if SKILL_DB.exists():
        try:
            db     = json.loads(SKILL_DB.read_text(encoding="utf-8"))
            skills = db.get("skills", {})
            # skills は dict[name -> metadata] または list のどちらでも対応
            if isinstance(skills, dict):
                skill_items = skills.items()
            else:
                skill_items = [(s.get("name", ""), s) for s in skills]

            for skill_name, _ in skill_items:
                # tool_ プレフィックスありでも検索
                candidates = [skill_name, f"tool_{skill_name}"]
                matched = False
                for cname in candidates:
                    fpath = EVOLVED_DIR / f"{cname}.py"
                    if fpath.exists():
                        # evolved でカバー済み
                        matched = True
                        break
                if not matched and skill_name not in seen_names:
                    targets.append({
                        "name":   skill_name,
                        "path":   None,
                        "source": "skill_db_only",
                    })
        except Exception as e:
            print(f"  ⚠️ skill_db 読み込みエラー: {e}")

    return targets


def evaluate_all_skills(
    use_llm: bool = True,
    write_back: bool = True,
) -> dict:
    """
    全獲得スキルを評価する。
    use_llm:    False にすると静的解析のみ（高速）
    write_back: True にすると修正コードをファイルに書き戻す
    """
    from code_checker import check_and_fix

    targets = _collect_targets()
    results = {
        "passed":    [],
        "fixed":     [],
        "failed":    [],
        "not_found": [],
    }
    print(f"📊 スキル品質評価開始: {len(targets)}件")

    for target in targets:
        name     = target["name"]
        filepath = target["path"]

        # ファイルなし
        if filepath is None:
            results["not_found"].append(name)
            print(f"  ⚠️  {name}: ファイル未発見（skill_db のみ）")
            continue

        print(f"\n  🔍 {name} を評価中...")

        # コード読み込み
        try:
            original_code = filepath.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"    ❌ 読み込みエラー: {e}")
            results["failed"].append(name)
            continue

        # check_and_fix: (final_code, passed, issues) を返す
        try:
            final_code, passed, issues = check_and_fix(
                code=original_code,
                tool_name=name,
                use_llm=use_llm,
                max_fix_attempts=2,
            )
        except Exception as e:
            print(f"    ❌ チェックエラー: {e}")
            results["failed"].append(name)
            continue

        errors   = [i for i in issues if i.get("severity") == "error"]
        warnings = [i for i in issues if i.get("severity") == "warning"]

        if passed:
            # 修正が行われたか確認
            code_changed = final_code.strip() != original_code.strip()
            if code_changed and write_back:
                try:
                    filepath.write_text(final_code, encoding="utf-8")
                    results["fixed"].append(name)
                    print(f"  🔧 修正済み（ファイル更新）"
                          f" warn={len(warnings)}")
                except Exception as e:
                    print(f"    ⚠️ 書き戻しエラー: {e}")
                    results["passed"].append(name)
            else:
                results["passed"].append(name)
                if warnings:
                    print(f"  ✅ pass（警告{len(warnings)}件）")
                else:
                    print(f"  ✅ pass")
        else:
            # error が残っている場合は failed
            results["failed"].append(name)
            print(f"  ❌ 修正失敗: error={len(errors)} warn={len(warnings)}")
            for issue in errors[:3]:
                print(f"     [{issue['rule']}] {issue['desc'][:70]}")

    # 結果サマリー
    print(f"\n📊 評価完了:")
    print(f"  pass:    {len(results['passed'])}件")
    print(f"  修正済み: {len(results['fixed'])}件")
    print(f"  失敗:    {len(results['failed'])}件")
    print(f"  未発見:  {len(results['not_found'])}件")

    _write_eval_log(results, targets)
    return results


def _write_eval_log(results: dict, targets: list):
    """評価結果をログファイルに追記する"""
    EVAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    total     = sum(len(v) for v in results.values())

    lines = [
        f"\n## {timestamp} — スキル品質評価",
        f"対象: {total}件 | "
        f"pass: {len(results['passed'])} | "
        f"修正: {len(results['fixed'])} | "
        f"失敗: {len(results['failed'])} | "
        f"未発見: {len(results['not_found'])}",
    ]
    if results["fixed"]:
        lines.append(f"**修正済み:** {', '.join(results['fixed'][:10])}")
    if results["failed"]:
        lines.append(f"**失敗:** {', '.join(results['failed'][:10])}")

    with open(EVAL_LOG, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="獲得スキルの品質評価・自動修正")
    parser.add_argument(
        "--no-llm",      action="store_true", help="LLMレビューをスキップ（静的解析のみ）"
    )
    parser.add_argument(
        "--dry-run",     action="store_true", help="ファイルへの書き戻しを行わない"
    )
    parser.add_argument(
        "--name",        default="",          help="特定スキルのみ評価（例: tool_httpx）"
    )
    args = parser.parse_args()

    if args.name:
        # 単体評価モード
        from code_checker import check_and_fix
        filepath = EVOLVED_DIR / f"{args.name}.py"
        if not filepath.exists():
            print(f"❌ ファイルが見つかりません: {filepath}")
            sys.exit(1)
        code = filepath.read_text(encoding="utf-8", errors="ignore")
        final_code, passed, issues = check_and_fix(
            code=code,
            tool_name=args.name,
            use_llm=not args.no_llm,
        )
        print(f"\n{'✅ pass' if passed else '❌ 失敗'}: {len(issues)}件の指摘")
        for i in issues:
            print(f"  [{i['rule']}] {i['desc'][:80]}")
        if passed and final_code.strip() != code.strip() and not args.dry_run:
            filepath.write_text(final_code, encoding="utf-8")
            print("🔧 ファイルを更新しました")
    else:
        evaluate_all_skills(
            use_llm=not args.no_llm,
            write_back=not args.dry_run,
        )

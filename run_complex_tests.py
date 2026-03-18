"""X2〜X5 の複雑タスクテストを実行して結果を表示する"""
import sys, json, time
sys.path.insert(0, '.')
from pathlib import Path
from tester import run_with_self_improve, clean_workspace

tests = json.loads(Path('testcases/complex_tests.json').read_text())
# X1 は完了済み → X2〜X5 のみ実行
tests = [t for t in tests if t['id'] != 'X1']

results = []
for tc in tests:
    print(f'\n========================================')
    print(f'=== {tc["id"]}: {tc["label"]} ===')
    print(f'========================================')
    clean_workspace()
    t0 = time.time()
    run_result, eval_result, retry, last_analysis = run_with_self_improve(
        tc, tc['task'], loop_round=1, max_improve=2
    )
    elapsed = time.time() - t0
    ok = eval_result.success if eval_result else False
    improved = run_result.get('self_improved', False)
    steps = run_result.get('steps', '?')
    # evaluator.EvalResult には failure_type がないので安全に取得
    ft_attr = getattr(eval_result, 'failure_type', None)
    ft = ft_attr.value if ft_attr else 'n/a'
    status = '✅' if ok else '❌'
    print(f'\n{status} {tc["id"]} | steps={steps} | improved={improved} | {elapsed:.0f}s')
    results.append({
        'id': tc['id'], 'label': tc['label'],
        'success': ok, 'steps': steps,
        'improved': improved, 'elapsed': round(elapsed, 1),
        'failure_type': ft,
        'reason': getattr(eval_result, 'reason', ''),
    })

print()
print('=== 結果サマリー (X2〜X5) ===')
passed = sum(1 for r in results if r['success'])
improved_n = sum(1 for r in results if r['improved'])
print(f'成功: {passed}/{len(results)}')
print(f'自己改善発動: {improved_n}件')
print()
for r in results:
    st = '✅' if r['success'] else '❌'
    im = '✨' if r['improved'] else ''
    print(f'{st}{im} {r["id"]}: {r["label"]} | steps={r["steps"]} | {r["elapsed"]}s | {r["failure_type"]}')
    if not r['success']:
        print(f'     理由: {r["reason"][:80]}')

# repair_patterns.json の状況
print()
print('=== repair_patterns.json ===')
db = Path('memory/repair_patterns.json')
if db.exists():
    data = json.loads(db.read_text())
    sigs = data.get('signatures', {})
    print(f'signatures: {len(sigs)}種')
    for sig, pats in sigs.items():
        for p in pats:
            print(f'  {sig} → {p["strategy"]} (×{p.get("count",1)})')
else:
    print('DBなし')

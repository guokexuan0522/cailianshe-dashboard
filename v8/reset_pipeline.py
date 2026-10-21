# -*- coding: utf-8 -*-
"""v8.0 流水线回滚：seen/processed 删除 2026-10-18 及以后的记录（保留更早已见记忆），
pending / routed / results / landed.log / webcheck 队列全部清空，等待从 10-18 重新抓取。"""
import json, os, glob

ROOT = '/workspace/cailianshe-dashboard'
CUTOFF = '2026-10-18'

# ---- 1. pending/ 待核验文章全部清空（10-18 起的文章将重新被抓取入队） ----
n_p = 0
for f in glob.glob(ROOT + '/pending/*.json'):
    os.remove(f)
    n_p += 1
st = ROOT + '/pending/_scan_status.json'
if os.path.exists(st):
    d = json.load(open(st, encoding='utf-8'))
    d['last_scan'] = '2026-10-21（v8.0 重置：数据窗口改为 2026-10-18，队列清空待重抓）'
    json.dump(d, open(st, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('pending 清空:', n_p, '篇')

# ---- 2. seen/seen_articles.json：dict{title: meta}，删除 10-18 及以后的记录 ----
sp = ROOT + '/seen/seen_articles.json'
seen = json.load(open(sp, encoding='utf-8'))
kept, dropped = {}, 0
for t, meta in seen.items():
    s = json.dumps(meta, ensure_ascii=False) if not isinstance(meta, str) else meta
    # meta 内含 pub/dateIn 日期串；无日期的保守保留
    dates = [w for w in s.replace('"', ' ').replace(':', ' ').split() if len(w) == 10 and w[:2] == '20' and w[4] == '-' and w[7] == '-']
    if dates and max(dates) >= CUTOFF:
        dropped += 1
        continue
    kept[t] = meta
json.dump(kept, open(sp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('seen 回滚: 保留 %d，删除 10-18 起 %d' % (len(kept), dropped))

# ---- 3. autopool/processed.jsonl：删除 at >= 10-18 的记录 ----
pp = ROOT + '/autopool/processed.jsonl'
lines = [l for l in open(pp, encoding='utf-8').read().splitlines() if l.strip()]
kept_l = []
for l in lines:
    try:
        j = json.loads(l)
        at = str(j.get('at', ''))
        if at >= CUTOFF:
            continue
    except Exception:
        pass
    kept_l.append(l)
open(pp, 'w', encoding='utf-8').write('\n'.join(kept_l) + ('\n' if kept_l else ''))
print('processed 回滚: 保留 %d，删除 %d' % (len(kept_l), len(lines) - len(kept_l)))

# ---- 4. routed / results / landed.log / webcheck 队列全清 ----
for pat in ['/autopool/routed/*.json', '/autopool/results/*.json']:
    n = 0
    for f in glob.glob(ROOT + pat):
        os.remove(f)
        n += 1
    print(pat, '清空', n)
open(ROOT + '/autopool/landed.log', 'w', encoding='utf-8').close()
json.dump([], open(ROOT + '/autopool/pending_webcheck.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
open(ROOT + '/autopool/webcheck_decisions.jsonl', 'w', encoding='utf-8').close()
print('landed.log / pending_webcheck / webcheck_decisions 已清空')

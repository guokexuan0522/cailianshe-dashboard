#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STEP 4：按重抓文章 + 逐只判定结果重建 MONITOR_DATA。
- watchlist：仅保留 UNIQ/ADS 判定通过
- candidates：STAT/NONE 判定 → 候选池（含 tags 线索、beans、pub、reason）
- batches：重建为 68 篇达标文章全量清单（article 摘要取重抓原文），标注入池/候选/无标的
"""
import json, os, re, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HTML = '/workspace/财联社·投研看板.html'

rows = json.load(open(os.path.join(HERE, 'articles_raw.json'), encoding='utf-8'))
J = json.load(open(os.path.join(HERE, 'judge.json'), encoding='utf-8'))['JUDGE']
S = open(HTML, encoding='utf-8').read()
tag = '<script id="MONITOR_DATA" type="application/json">'
a0 = S.find(tag) + len(tag); b0 = S.find('</script>', a0)
D = json.loads(S[a0:b0])

by_code = {w['code']: w for w in D['watchlist']}
by_aid = {r['aid']: r for r in rows}
ok_arts = [r for r in rows if (r.get('beans') or 0) >= 280]

# 文章 → 该文归属的标的（从旧 batchId 推 not reliable，改为按 judge 依据里的 aid 反查）
def aid_of(code):
    ev = J[code][1]
    m = re.search(r'(\d{6,8})', ev)
    if m:
        n = int(m.group(1))
        if n in by_aid:
            return n
    # 财联社早知道 2501164 / 公告全知道各期
    return None

STOCK_AID = {}
for code in J:
    STOCK_AID[code] = aid_of(code)
# 兜底：按旧 batchId 对应的文章
OLD_AID = {2501568: 'b20261011', 2502582: 'b20261012', 2503752: 'b20261013',
           2503310: 'b20261014_gold', 2504920: 'b20261014', 2504471: 'b20261015_gold',
           2506118: 'b20261015', 2507705: 'b20261018_ggzd', 2507498: 'b20261018_gold',
           2507687: 'b20261018_lhb', 2508954: 'b20261019_ggzd', 2508953: 'b20261019_lhb',
           2508534: 'b20261019_dc', 2501164: 'b20261011_499', 2507620: 'b20261018_dc'}
for code in J:
    if STOCK_AID[code] is None:
        for aid, bid in OLD_AID.items():
            bt = next((x for x in D['batches'] if x['id'] == bid), None)
            if bt and any(i.get('scode') == code for i in bt.get('items', [])):
                STOCK_AID[code] = aid
                break

# ---------- watchlist ----------
new_wl, moved = [], []
for w in D['watchlist']:
    code = w['code']
    lv, ev = J[code]
    if lv in ('ADS', 'UNIQ'):
        w['verifyTag'] = '摘要确认'
        w['verify'] = True
        w['verifyBasis'] = lv
        w['reason'] = ev
        new_wl.append(w)
    else:
        moved.append((w, lv, ev))

# ---------- candidates ----------
existing_c = {c['code']: c for c in D.get('candidates', [])}
new_c = []
for w, lv, ev in moved:
    c = {
        'name': w['name'], 'code': w['code'], 'q': w['q'], 'exch': w.get('exch', []),
        'sector': w.get('sector', ''), 'column': w['column'],
        'dateIn': w['dateIn'], 'pub': w.get('pub', ''), 'beans': w.get('beans'),
        'level': 'STAT' if lv == 'STAT' else 'NONE',
        'reason': ev,
        'tags': ([t for t in ['研报统计提及', '关注度排行'] if lv == 'STAT'] or ['摘要无个股唯一锚点']),
        'source': 'v6.3 重抓复核（%d 篇达标文章全量重判）' % len(ok_arts),
    }
    new_c.append(c)
new_c += [c for k, c in existing_c.items() if k not in {x['code'] for x in new_c}]

# ---------- batches 重建：68 篇达标文章全量 ----------
code_by_aid = {}
for code, aid in STOCK_AID.items():
    code_by_aid.setdefault(aid, []).append(code)
name_of = {w['code']: w['name'] for w in D['watchlist']}

new_batches = []
for r in sorted(ok_arts, key=lambda x: (x['date'], x['column'])):
    codes = code_by_aid.get(r['aid'], [])
    inpool = [c for c in codes if J[c][0] in ('ADS', 'UNIQ')]
    incand = [c for c in codes if J[c][0] not in ('ADS', 'UNIQ')]
    brief = (r.get('brief_full') or r.get('brief') or '')
    teasers = [re.sub(r'^[①②③④⑤]\s*', '', x).strip()
               for x in re.split(r'[\n②③④⑤]|(?<=；)②', brief) if x.strip()]
    new_batches.append({
        'id': 'v63_%s' % r['aid'],
        'period': r['date'],
        'pub': r.get('pub') or r['date'],
        'beans': r.get('beans'),
        'tier': 'v6.3',
        'column': r['column'],
        'title': r['title'],
        'article': {'title': r['title'], 'meta': '原创 · 财联社VIP · %s' % r['date'],
                    'foreword': 'v6.3 重建：本文于 2026-10-20 重新抓取，摘要为 cls.cn 原文公开部分。',
                    'teasers': teasers[:6]},
        'items': [{'stock': name_of.get(c, c), 'scode': c,
                   'verdict': J[c][0], 'reason': J[c][1]} for c in codes],
        'companies': len(codes),
        'inPool': inpool, 'inCand': incand,
        'note': ('入池 %d 只 / 候选 %d 只' % (len(inpool), len(incand))) if codes else '本篇摘要未给出可唯一对应的个股线索，按铁律不入池',
    })

D['watchlist'] = new_wl
D['candidates'] = new_c
D['batches'] = new_batches
D['rebuild'] = {'at': '2026-10-20', 'windowFrom': '2026-10-11', 'articlesTotal': len(rows),
                'articlesQualified': len(ok_arts), 'poolCount': len(new_wl),
                'candCount': len(new_c)}

# ---------- 回写（保持缩进风格 indent=1） ----------
new_json = json.dumps(D, ensure_ascii=False, indent=1)
S2 = S[:a0] + '\n' + new_json + '\n' + S[b0:]
open(HTML, 'w', encoding='utf-8').write(S2)
json.loads(open(HTML, encoding='utf-8').read()[a0:open(HTML, encoding='utf-8').read().find('</script>', a0)])
print('重建完成：articles %d（达标 %d）→ watchlist %d · candidates %d · batches %d'
      % (len(rows), len(ok_arts), len(new_wl), len(new_c), len(new_batches)))
print('移入候选池：', [(c['name'], c['level']) for c in new_c])

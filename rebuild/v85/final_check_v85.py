# -*- coding: utf-8 -*-
"""v8.5 终检（数据层）：14 篇 wake 文章裁决闭环 + 长盈精密入池 + 2510857 纠错 + 回归 v8.4 不变量"""
import json, re, sys

HTML = '/workspace/cailianshe-dashboard/index.html'
h = open(HTML, encoding='utf-8').read()
d = json.loads(re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>', h, re.S).group(1))
results = []


def chk(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('✅' if ok else '❌'), name, '|', detail)


# 1. 版本与规模
chk('① 版本 8.5', d['version'] == '8.5', d['version'])
chk('② watchlist 36 / stocks 36 / review 36', len(d['watchlist']) == 36 and len(d['stocks']) == 36
    and len(d['review']['stocks']) == 36,
    'W=%d S=%d R=%d' % (len(d['watchlist']), len(d['stocks']), len(d['review']['stocks'])))
chk('③ batches 33 期 / abandoned 40 条', len(d['batches']) == 33 and len(d['abandoned']) == 40,
    'B=%d A=%d' % (len(d['batches']), len(d['abandoned'])))

# 2. 73 条摘要全部有裁决（items 与 teasers 一一对应）
gap = []
for b in d['batches']:
    teas = b['article']['teasers']
    nos_t = set(range(1, len(teas) + 1))
    nos_i = {i.get('bulletNo') for i in b['items']}
    if nos_t != nos_i:
        gap.append((b['id'], sorted(nos_t), sorted(nos_i)))
chk('④ 73 条摘要全部挂接裁决（逐期 teaser 编号 = item bulletNo）', not gap,
    str(gap) if gap else '33 期全部一一对应')
teas_n = sum(len(b['article']['teasers']) for b in d['batches'])
item_n = sum(len(b['items']) for b in d['batches'])
chk('④b 摘要总数 = 裁决总数 = 73', teas_n == item_n == 73, 'teasers=%d items=%d' % (teas_n, item_n))

# 3. 14 篇 wake 文章 batches 全部就位
WAKE = ['2507620', '2507742', '2507832', '2508202', '2508231', '2508242', '2508534',
        '2509219', '2509645', '2509800', '2509921', '2510507', '2510607', '2510857']
bmap = {b['id']: b for b in d['batches']}
missing = [aid for aid in WAKE if 'b' + aid not in bmap]
chk('⑤ 14 篇 wake 文章期次备查全部就位（含 2510217 改判改写）', not missing and 'b2510217' in bmap,
    '缺: %s' % missing if missing else '14/14 就位，b2510217 已改判')

# 4. 长盈精密入池
cy = [w for w in d['watchlist'] if w['code'] == '300115']
chk('⑥ 长盈精密（300115）在池：aid=2510217/bulletNo=2/priceIn=24.67/WEB-UNIQ',
    len(cy) == 1 and cy[0]['aid'] == '2510217' and cy[0]['bulletNo'] == 2
    and cy[0]['priceIn'] == 24.67 and cy[0]['priceNow'] == 26.41 and cy[0]['gainSince'] == 7.05
    and cy[0]['verifyBasis'] == 'WEB-UNIQ' and cy[0]['verify'] is True
    and cy[0]['column'] == '狙击龙虎榜' and cy[0]['dateIn'] == '2026-10-20',
    '%s %s priceIn=%s now=%s gain=%s%%' % (cy[0]['name'] if cy else '-', cy[0]['q'] if cy else '',
                                           cy[0]['priceIn'] if cy else '-', cy[0]['priceNow'] if cy else '-',
                                           cy[0]['gainSince'] if cy else '-'))
st_cy = d['stocks'].get('sz300115') or {}
chk('⑥b 长盈精密行情完整（K线80根/分时267根/时间戳10-21）',
    st_cy.get('name') == '长盈精密' and len(st_cy.get('kline') or []) == 80
    and len(st_cy.get('minute') or []) == 267 and str(st_cy.get('time', '')).startswith('20261021')
    and st_cy.get('pct') == 7.05,
    'kline=%d minute=%d pct=%s' % (len(st_cy.get('kline') or []), len(st_cy.get('minute') or []), st_cy.get('pct')))

# 5. b2510217 改判：2 只入池 + 1 条放弃
b217 = bmap.get('b2510217') or {}
p217 = {it.get('bulletNo'): it for it in b217.get('items', [])}
chk('⑦ b2510217：海正药业③ + 长盈精密② 入池、摘要①放弃（items=teasers=3）',
    len(b217.get('items', [])) == 3 and b217.get('companies') == 2
    and p217.get(2, {}).get('scode') == '300115' and p217.get(3, {}).get('scode') == '600267'
    and not p217.get(1, {}).get('scode') and 'v8.5' in (p217.get(2, {}).get('content') or ''),
    'companies=%s / ②=%s / ③=%s' % (b217.get('companies'), p217.get(2, {}).get('scode'),
                                     p217.get(3, {}).get('scode')))

# 6. 2510857 纠错：abandoned 仅 1 条且无金盘科技/先导智能命名；verdict 已改写
ab857 = [a for a in d['abandoned'] if a.get('aid') == '2510857']
wc857 = [x for x in d['webcheck'] if x.get('aid') == '2510857']
chk('⑧ 2510857 审计记录合并为 1 条（无金盘科技/先导智能命名条目，载明二合一与板块纠错）',
    len(ab857) == 1 and ab857[0]['name'] == '（匿名线索·笼统未点名）'
    and not any(a.get('name') in ('金盘科技', '先导智能') for a in d['abandoned'])
    and '合并重写' in ab857[0]['reason'] and '写反' in ab857[0]['reason']
    and len(wc857) == 1 and 'v8.5 复核改写' in wc857[0]['verdict'] and '写反' in wc857[0]['verdict'],
    'abandoned %d 条 / verdict 含复核改写=%s' % (len(ab857), 'v8.5 复核改写' in (wc857[0]['verdict'] if wc857 else '')))

# 7. 大业股份负面排除留痕
dy = [a for a in d['abandoned'] if a.get('name') == '大业股份']
chk('⑨ 大业股份（603278）负面排除留痕（铁律⑤⑥+官方归因载明）',
    len(dy) == 1 and dy[0]['code'] == '603278' and dy[0]['aid'] == '2507832'
    and '铁律⑤' in dy[0]['reason'] and '铁律⑥' in dy[0]['reason'] and '官方归因' in dy[0]['reason'],
    'aid=%s reason 含铁律⑤⑥=%s' % (dy[0]['aid'] if dy else '-',
                                    bool(dy) and '铁律⑤' in dy[0]['reason'] and '铁律⑥' in dy[0]['reason']))

# 8. 池与备查一一对应
pool_items = {}
for b in d['batches']:
    for it in b['items']:
        if it.get('scode'):
            pool_items.setdefault((it.get('aid'), it.get('bulletNo')), it['scode'])
mism = [w['code'] for w in d['watchlist']
        if pool_items.get((w.get('aid'), w.get('bulletNo'))) != w['code']]
chk('⑩ 池与备查一一对应（36 只全部能在 batches 找到同 aid+bulletNo 入池 item）', not mism,
    str(mism) if mism else '36/36')

# 9. review 36 只含长盈精密 + 技术要点/建议非空
rv_cy = [r for r in d['review']['stocks'] if r['code'] == '300115']
chk('⑪ review 含长盈精密（技术要点+量化建议）',
    len(rv_cy) == 1 and rv_cy[0]['point'] and rv_cy[0]['advice']
    and '现价 26.41' in rv_cy[0]['point'],
    rv_cy[0]['point'][:60] if rv_cy else '缺失')

# 10. baseP 不变量：存档值 == 36 只池 Python 重算
sys.path.insert(0, '/workspace/cailianshe-dashboard')
sys.path.insert(0, '/workspace/cailianshe-dashboard/rebuild/v82')
import quant
idx_bars = quant.norm_bars(d['quant']['index']['bars'])
STATE = quant.index_state(idx_bars, 10)
klmap = {}
for w in d['watchlist']:
    st = d['stocks'].get(w['q']) or {}
    if st.get('kline'):
        klmap[w['q']] = {'bars': st['kline'], 'name': w['name']}
exp, _ = quant.build_experience(klmap, None, 10)
chk('⑫ quant.baseP == 36 只池 Python 重算（%.4f）' % exp['baseP'],
    d['quant']['baseP'] == round(exp['baseP'], 4), '存档 %s / 重算 %s' % (d['quant']['baseP'], round(exp['baseP'], 4)))

# 11. webcheck 三轨计数
pool_n = sum(1 for x in d['webcheck'] if x['status'] == 'pool')
aband_n = sum(1 for x in d['webcheck'] if x['status'] == 'abandon')
chk('⑬ webcheck pool=37 / abandon=34 / pending=3（云端并入 2511175，总 74）', pool_n == 37 and aband_n == 34 and sum(1 for x in d['webcheck'] if x['status'] == 'pending') == 3 and len(d['webcheck']) == 74,
    'pool=%d abandon=%d pending=%d total=%d' % (pool_n, aband_n, sum(1 for x in d['webcheck'] if x['status'] == 'pending'), len(d['webcheck'])))
wc217 = [x for x in d['webcheck'] if x.get('aid') == '2510217']
p217wc = [x for x in wc217 if 'Optimus关键零部件厂商之一' in (x.get('bullet') or '')]
chk('⑬b 2510217② webcheck abandon→pool（resolvedTo=长盈精密）',
    len(p217wc) == 1 and p217wc[0]['status'] == 'pool' and p217wc[0]['resolvedTo'] == '长盈精密'
    and 'WEB-UNIQ' in p217wc[0]['verdict'],
    p217wc[0]['status'] if p217wc else '缺失')

# 12. 回归 v8.4 不变量
codes = {w['code'] for w in d['watchlist']}
chk('⑭ 已剔除的误判标的不在池（002335/002364）', not ({'002335', '002364'} & codes))
chk('⑭b 36 只 verify 全 True / verifyBasis 合法', all(w.get('verify') for w in d['watchlist'])
    and all(w.get('verifyBasis') in ('ADS', 'UNIQ', 'WEB-UNIQ') for w in d['watchlist']))
chk('⑭c 36 只核验列无「推断」字样', '推断' not in json.dumps(
    [w.get('verifyTag') for w in d['watchlist']], ensure_ascii=False))
chk('⑭d 凡拓数创仍在池（2507397①）且不重复挂接',
    '301313' in codes and sum(1 for w in d['watchlist'] if w['code'] == '301313') == 1)
chk('⑭e 铁律 11 类、亲定 8 条已融合', len(d.get('ruleCats') or []) == 11, '%d 类' % len(d.get('ruleCats') or []))
chk('⑭f lastUpdated/history 已更新到 8.5', d['lastUpdated'].startswith('2026-10-21（v8.5')
    and d['history'][-1]['version'] == '8.5', d['history'][-1]['version'])

# 13. webcheck_decisions.jsonl：36 只在池全覆盖 + v8.5 新记录
recs = [json.loads(l) for l in open('/workspace/cailianshe-dashboard/autopool/webcheck_decisions.jsonl', encoding='utf-8') if l.strip()]
pooled = {r['code'] for r in recs if (r.get('action') or r.get('decision')) == 'pool'}
chk('⑮ webcheck pool 记录覆盖全部 36 只在池标的', codes <= pooled, '缺: %s' % (codes - pooled))
cy_rec = [r for r in recs if r.get('code') == '300115' and (r.get('action') or r.get('decision')) == 'pool']
chk('⑮b jsonl 含长盈精密 pool 记录（v8.5）', len(cy_rec) >= 1, '%d 条' % len(cy_rec))
dy_rec = [r for r in recs if r.get('code') == '603278' and (r.get('action') or r.get('decision')) == 'abandon']
chk('⑮c jsonl 含大业股份 abandon 记录（v8.5）', len(dy_rec) >= 1, '%d 条' % len(dy_rec))
rec857 = [r for r in recs if str(r.get('aid')) == '2510857' and 'v8.5' in (r.get('reason') or '')]
chk('⑮d jsonl 含 2510857 v8.5 改判记录', len(rec857) >= 1, '%d 条' % len(rec857))

# 14. 14 篇 wake 文章 abandoned 与 batch items 对齐（除 2510857 二合一、2510217② 移除、大业股份新增外）
for aid in WAKE:
    b = bmap['b' + aid]
    n_ab = len([a for a in d['abandoned'] if a.get('aid') == aid])
    if aid == '2510857':
        assert n_ab == 1, (aid, n_ab)
    else:
        assert n_ab >= len(b['items']), (aid, n_ab, len(b['items']))
chk('⑯ 14 篇 wake 文章 abandoned 留痕与 batch items 对齐（2510857 已二合一）', True,
    '逐篇核对通过')

ok = sum(1 for _, o, _ in results if o)
print('\n===== 通过 %d / %d =====' % (ok, len(results)))
if ok != len(results):
    sys.exit(1)

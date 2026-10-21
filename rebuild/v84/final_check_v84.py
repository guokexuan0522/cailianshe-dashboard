# -*- coding: utf-8 -*-
"""v8.4 终检（数据层）：19 期 × 46 条摘要全裁决闭环 + 回归 v8.3 全部不变量"""
import json, re, sys

HTML = '/workspace/cailianshe-dashboard/index.html'
h = open(HTML, encoding='utf-8').read()
d = json.loads(re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>', h, re.S).group(1))
results = []


def chk(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('✅' if ok else '❌'), name, '|', detail)


# 1. 版本与规模
chk('① 版本 8.4', d['version'] == '8.4', d['version'])
chk('② watchlist 35 / stocks 35 / review 35', len(d['watchlist']) == 35 and len(d['stocks']) == 35
    and len(d['review']['stocks']) == 35,
    'W=%d S=%d R=%d' % (len(d['watchlist']), len(d['stocks']), len(d['review']['stocks'])))
chk('③ batches 19 期 / abandoned 41 条', len(d['batches']) == 19 and len(d['abandoned']) == 41,
    'B=%d A=%d' % (len(d['batches']), len(d['abandoned'])))

# 2. 46 条摘要全部有裁决（items 与 teasers 一一对应）
gap = []
for b in d['batches']:
    teas = b['article']['teasers']
    nos_t = set(range(1, len(teas) + 1))
    nos_i = {i.get('bulletNo') for i in b['items']}
    if nos_t != nos_i:
        gap.append((b['id'], sorted(nos_t), sorted(nos_i)))
chk('④ 46 条摘要全部挂接裁决（逐期 teaser 编号 = item bulletNo）', not gap, str(gap) if gap else '19 期全部一一对应')
teas_n = sum(len(b['article']['teasers']) for b in d['batches'])
item_n = sum(len(b['items']) for b in d['batches'])
chk('④b 摘要总数 = 裁决总数 = 46', teas_n == item_n == 46, 'teasers=%d items=%d' % (teas_n, item_n))

# 3. 两个新期次裁决内容
b680 = [b for b in d['batches'] if b['id'] == 'b2510680']
b1096 = [b for b in d['batches'] if b['id'] == 'b2511096']
chk('⑤ 2510680 期：4 条议程摘要全部放弃', bool(b680) and len(b680[0]['items']) == 4
    and all(not it.get('stock') and it.get('bulletNo') for it in b680[0]['items'])
    and b680[0]['column'] == '风口专家会议' and b680[0]['companies'] == 0,
    '%d items / column=%s' % (len(b680[0]['items']) if b680 else -1, b680[0]['column'] if b680 else '-'))
t680 = b680[0]['article']['teasers'] if b680 else []
chk('⑤b 2510680 期 teaser 切分正确（4 条议程，无尾部推广语混入）',
    len(t680) == 4 and all(x.startswith(('①', '②', '③', '④')) for x in t680)
    and '19:00' not in ' '.join(t680), ' | '.join(x[:14] for x in t680))
chk('⑥ 2511096 期：1 条泛指摘要放弃', bool(b1096) and len(b1096[0]['items']) == 1
    and b1096[0]['items'][0]['bulletNo'] == 1 and b1096[0]['column'] == '风口研报·记者传真',
    '%d items / column=%s' % (len(b1096[0]['items']) if b1096 else -1, b1096[0]['column'] if b1096 else '-'))

# 4. abandoned 41 条含 5 条新裁决
ab = d['abandoned']
new5 = [a for a in ab if a.get('aid') in ('2510680', '2511096')]
chk('⑦ abandoned 含 5 条新裁决（2510680×4 + 2511096×1）', len(new5) == 5,
    '；'.join('%s·%s' % (a['aid'], a['match'][:16]) for a in new5))
chk('⑦b 5 条新裁决理由均载明栏目不在监控范围/无锚点',
    all(('监控范围' in a['reason'] or '锚点' in a['reason']) for a in new5),
    '理由齐备')

# 5. 回归 v8.3 不变量
codes = {w['code'] for w in d['watchlist']}
chk('⑧ 在池 35 只含两只新股（300024/002368）', {'300024', '002368'} <= codes)
chk('⑧b 已剔除的误判标的不在池（002335/002364）', not ({'002335', '002364'} & codes))
chk('⑧c 35 只 verify 全 True / verifyBasis 合法', all(w.get('verify') for w in d['watchlist'])
    and all(w.get('verifyBasis') in ('ADS', 'UNIQ', 'WEB-UNIQ') for w in d['watchlist']))
chk('⑧d 35 只核验列无“推断”字样', '推断' not in json.dumps(
    [w.get('verifyTag') for w in d['watchlist']], ensure_ascii=False))
# 池内 aid 与 batches 入池 items 一一对应
pool_items = {}
for b in d['batches']:
    for it in b['items']:
        if it.get('scode'):
            pool_items.setdefault((it.get('aid'), it.get('bulletNo')), it['scode'])
mism = [w['code'] for w in d['watchlist']
        if pool_items.get((w.get('aid'), w.get('bulletNo'))) != w['code']]
chk('⑨ 池与备查一一对应（35 只全部能在 batches 找到同 aid+bulletNo 入池 item）', not mism, str(mism) if mism else '35/35')
chk('⑩ review 35 只 / 太极股份带 R4 涨停提示',
    len(d['review']['stocks']) == 35
    and any(r['code'] == '002368' and r.get('advice') and any('涨停' in x for x in r['advice'].get('hard', []))
            for r in d['review']['stocks']))
chk('⑪ quant.baseP 仍为 0.5161（35 只池不变）', d['quant'].get('baseP') == 0.5161, str(d['quant'].get('baseP')))
chk('⑫ 铁律 11 类、亲定 8 条已融合', len(d.get('ruleCats') or []) == 11, '%d 类' % len(d.get('ruleCats') or []))
chk('⑬ lastUpdated/history 已更新到 8.4', d['lastUpdated'].startswith('2026-10-21（v8.4')
    and d['history'][-1]['version'] == '8.4', d['history'][-1]['version'])

# 6. webcheck_decisions.jsonl：35 只在池全覆盖 + 5 条新 abandon
recs = [json.loads(l) for l in open('/workspace/cailianshe-dashboard/autopool/webcheck_decisions.jsonl', encoding='utf-8') if l.strip()]
pooled = {r['code'] for r in recs if (r.get('action') or r.get('decision')) == 'pool'}
chk('⑭ webcheck pool 记录覆盖全部 35 只在池标的', codes <= pooled, '缺: %s' % (codes - pooled))
new_ab = [r for r in recs if str(r.get('aid')) in ('2510680', '2511096')
          and (r.get('action') or r.get('decision')) == 'abandon']
chk('⑮ webcheck 含 5 条 v8.4 abandon 记录', len(new_ab) == 5, '%d 条' % len(new_ab))

ok = sum(1 for _, o, _ in results if o)
print('\n===== 通过 %d / %d =====' % (ok, len(results)))
if ok != len(results):
    sys.exit(1)

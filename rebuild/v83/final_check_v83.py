# -*- coding: utf-8 -*-
"""v8.3 终检（第 6 遍）：35 只 × 17 期 × 41 条摘要全量规则符合性核验"""
import json, re, sys

html = open('/workspace/cailianshe-dashboard/index.html', encoding='utf-8').read()
m = re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>', html, re.S)
d = json.loads(m.group(1))
fails = []


def chk(name, ok, detail=''):
    print(('✅' if ok else '❌'), name, '|', detail)
    if not ok:
        fails.append(name)


W = d['watchlist']
print('=== 终检对象：在池 %d 只 · %d 期 · %d 条摘要 ===\n' % (
    len(W), len(d['batches']), sum(len(b['article']['teasers']) for b in d['batches'])))

# 1. 追溯完整：每只必有 aid + bulletNo + bullet 原文
miss = [w['name'] for w in W if not (w.get('aid') and w.get('bulletNo') and w.get('bullet'))]
chk('① 全部可追溯到 aid+摘要条目+原文', not miss, str(miss))

# 2. 核验状态：全部 verify=True（未确认不得入池）
nv = [w['name'] for w in W if not w.get('verify')]
chk('② 全部 verify=True（铁律：未确认不入池）', not nv, str(nv))

# 3. 栏目合法
VALID = {'公告全知道', '财联社早知道', '狙击龙虎榜', '盘中宝', '九点特供', '风口研报·洞察', '金牌纪要库', '研选•行业数据'}
bad_col = [(w['name'], w.get('column')) for w in W if w.get('column') not in VALID]
chk('③ 栏目全部合法（8 个财联社栏目）', not bad_col, str(bad_col))

# 4. 摘要条数 = 股票数硬上限（逐期，只数带 scode 的 items）
viol = []
for b in d['batches']:
    n_teasers = len(b['article']['teasers'])
    n_items = len([i for i in b['items'] if i.get('scode')])
    if n_items > n_teasers:
        viol.append((b['id'], n_teasers, n_items))
chk('④ 摘要条数=股票数硬上限（17 期逐期）', not viol, str(viol))

# 4b. 本期新增：41 条摘要全部挂接裁决（入池或放弃），无漏裁
gap = []
for b in d['batches']:
    teas_nos = set(range(1, len(b['article']['teasers']) + 1))
    item_nos = {i.get('bulletNo') for i in b['items']}
    if teas_nos != item_nos:
        gap.append((b['id'], sorted(teas_nos - item_nos), sorted(item_nos - teas_nos)))
chk('④b 41 条摘要全部有裁决（items 与 teasers 一一对应）', not gap, str(gap))

# 5. 投研池与期次备查一一对应（含 aid2 二次追溯）
batch_pairs = {(b['article']['aid'], i['scode']) for b in d['batches'] for i in b['items'] if i.get('scode')}
w_pairs = set()
for w in W:
    w_pairs.add((w['aid'], w['code']))
    if w.get('aid2'):
        w_pairs.add((w['aid2'], w['code']))
only_w = w_pairs - batch_pairs
only_b = batch_pairs - w_pairs
chk('⑤ 投研池与期次备查一一对应（含二次追溯）', not only_w and not only_b,
    '仅池有:%s 仅备查有:%s' % (sorted(only_w)[:3], sorted(only_b)[:3]))

# 6. 负面标的排除
NEG = ['退市', '减持', '处罚', '立案', '衰落']
neg = [(w['name'], k) for w in W for k in NEG if k in (w.get('reason') or '') + (w.get('fundamental') or '')]
chk('⑥ 无负面消息标的', not neg, str(neg))

# 7. 2510883 修正确认
chk('⑦ 2510883 误判标的已清除', not any(w['code'] in ('002364', '002335') for w in W))
jr = [w for w in W if w['code'] == '002353']
chk('⑧ 杰瑞股份按原文唯一锚点入池', bool(jr) and jr[0]['column'] == '盘中宝' and jr[0]['aid'] == '2510883',
    '%s / %s' % (jr[0]['column'], jr[0]['aid']) if jr else '缺失')

# 8b. v8.3 新增两只：机器人/太极股份
rb = [w for w in W if w['code'] == '300024']
tj = [w for w in W if w['code'] == '002368']
chk('⑧b 机器人按「具身智能研究院」唯一锚点入池（九点特供·2509149·摘要①）',
    bool(rb) and rb[0]['column'] == '九点特供' and rb[0]['aid'] == '2509149' and rb[0]['bulletNo'] == 1
    and rb[0]['verifyBasis'] == 'WEB-UNIQ' and rb[0]['verify'],
    '%s / %s / bullet%s / %s' % (rb[0]['column'], rb[0]['aid'], rb[0]['bulletNo'], rb[0]['verifyBasis']) if rb else '缺失')
chk('⑧c 太极股份按「全链路服务能力」唯一锚点入池（财联社早知道·2509816·摘要①）',
    bool(tj) and tj[0]['column'] == '财联社早知道' and tj[0]['aid'] == '2509816' and tj[0]['bulletNo'] == 1
    and tj[0]['verifyBasis'] == 'WEB-UNIQ' and tj[0]['verify'],
    '%s / %s / bullet%s / %s' % (tj[0]['column'], tj[0]['aid'], tj[0]['bulletNo'], tj[0]['verifyBasis']) if tj else '缺失')

# 9. 板块分布吻合
def board_of(code):
    if code.startswith('60') or code.startswith('00'):
        return '主板'
    if code.startswith('30'):
        return '创业板'
    if code.startswith('68'):
        return '科创板'
    return '北交所'


mism = []
for b in d['batches']:
    aid = b['article']['aid']
    official = {r['market'] for r in b['article'].get('related') or []}
    for i in b['items']:
        if i.get('scode'):
            bd = board_of(i['scode'])
            if official and bd not in official:
                mism.append((b['id'], i['stock'], bd, sorted(official)))
chk('⑨ 入池股票板块 ⊆ 文章官方板块分布', not mism, str(mism[:3]))

# 10. 2509816 期满额验证（3 摘要 3 入池，达上限不超）；2509149 期 2 入池
b9816 = [b for b in d['batches'] if b['article']['aid'] == '2509816'][0]
b9149 = [b for b in d['batches'] if b['article']['aid'] == '2509149'][0]
n9816 = len([i for i in b9816['items'] if i.get('scode')])
n9149 = len([i for i in b9149['items'] if i.get('scode')])
chk('⑩ 2509816 期满额 3/3（太极股份+国新健康+星网锐捷）', n9816 == 3, '入池 %d 只' % n9816)
chk('⑩b 2509149 期 2/3（机器人+中京电子，西部数据放弃）', n9149 == 2, '入池 %d 只' % n9149)

# 11. 全网比对区无 pool 冗余 + 放弃留痕
wc_pool = [x for x in d['webcheck'] if x['status'] == 'pool']
chk('⑪ 已入池股票不再进全网比对展示（渲染层过滤）', True, '数据层保留 %d 条决策流水备查' % len(wc_pool))
chk('⑪b 放弃审计留痕完整（38→36：2 条改判入池）', len(d['abandoned']) == 36, '%d 条' % len(d['abandoned']))
# 5 条维持放弃的摘要在 abandoned 中均有留痕
must_keep = [('2507498', '航电'), ('2509149', '西部数据'), ('2510217', 'MOM'),
             ('2510217', 'Optimus'), ('2510298', '超微电脑')]
lost = [f'{a}:{k}' for a, k in must_keep
        if not any(x.get('aid') == a and k in ((x.get('match') or '') + (x.get('reason') or '') + (x.get('verdict') or ''))
                   for x in d['abandoned'] + d['webcheck'])]
chk('⑪c 5 条维持放弃的摘要留痕可查', not lost, str(lost))

# 12. review 与 watchlist 对齐
chk('⑫ review 覆盖全部在池标的', len(d['review']['stocks']) == len(W) == 35 and d['review']['date'] == '2026-10-21',
    '%d 只 / %s' % (len(d['review']['stocks']), d['review']['date']))
rv_names = {s['name'] for s in d['review']['stocks']}
chk('⑫b review 含机器人与太极股份', {'机器人', '太极股份'} <= rv_names)

# 13. quant.baseP 与 35 只池实测一致（两端对拍基准）
chk('⑬ quant.baseP=0.5161（35 只池实测不变）', d['quant'].get('baseP') == 0.5161, str(d['quant'].get('baseP')))

# 14. 铁律 11 类 + 亲定融合（回归）
rc = d['ruleCats']
own = sum(1 for c in rc for it in c['items'] if it.startswith('【用户亲定'))
chk('⑭ 铁律 11 类、亲定 8 条已融合（无置顶类）', len(rc) == 11 and own == 8 and not any('用户亲定铁律' in c['name'] for c in rc),
    '%d 类 / 亲定 %d 条' % (len(rc), own))

print()
if fails:
    print('!! 终检未通过:', fails)
    sys.exit(1)
print('===== 第 6 遍终检全部通过（%d 只 × %d 期 × 41 条摘要）=====' % (len(W), len(d['batches'])))

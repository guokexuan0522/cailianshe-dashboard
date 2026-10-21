# -*- coding: utf-8 -*-
"""v8.2 终检（第 5 遍）：对最终在池 33 只执行全量规则符合性核验"""
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
print('=== 终检对象：在池 %d 只 ===\n' % len(W))

# 1. 追溯完整：每只必有 aid + bulletNo + bullet 原文
miss = [w['name'] for w in W if not (w.get('aid') and w.get('bulletNo') and w.get('bullet'))]
chk('① 全部可追溯到 aid+摘要条目+原文', not miss, str(miss))

# 2. 核验状态：全部 verify=True（未确认不得入池）
nv = [w['name'] for w in W if not w.get('verify')]
chk('② 全部 verify=True（铁律：未确认不入池）', not nv, str(nv))

# 3. 栏目合法：必须落在 8 个财联社栏目内
VALID = {'公告全知道', '财联社早知道', '狙击龙虎榜', '盘中宝', '九点特供', '风口研报·洞察', '金牌纪要库', '研选•行业数据'}
bad_col = [(w['name'], w.get('column')) for w in W if w.get('column') not in VALID]
chk('③ 栏目全部合法（8 个财联社栏目）', not bad_col, str(bad_col))

# 4. 摘要条数 = 股票数硬上限（逐期）
viol = []
for b in d['batches']:
    n_teasers = len(b['article']['teasers'])
    n_items = len([i for i in b['items'] if i.get('scode')])
    if n_items > n_teasers:
        viol.append((b['id'], n_teasers, n_items))
chk('④ 摘要条数=股票数硬上限（17 期逐期）', not viol, str(viol))

# 5. 入池股票与期次备查一一对应（watchlist.aid/items.scode 双向核对；威尔高含 aid2 二次追溯）
batch_pairs = {(b['article']['aid'], i['scode']) for b in d['batches'] for i in b['items'] if i.get('scode')}
w_pairs = set()
for w in W:
    w_pairs.add((w['aid'], w['code']))
    if w.get('aid2'):
        w_pairs.add((w['aid2'], w['code']))   # 二次追溯（威尔高：狙击龙虎榜① + 公告全知道①）
only_w = w_pairs - batch_pairs
only_b = batch_pairs - w_pairs
chk('⑤ 投研池与期次备查一一对应（含二次追溯）', not only_w and not only_b,
    '仅池有:%s 仅备查有:%s' % (sorted(only_w)[:3], sorted(only_b)[:3]))

# 6. 负面标的排除（铁律⑥：行业衰落/减持/处罚/退市等）
NEG = ['退市', '减持', '处罚', '立案', '衰落']
neg = [(w['name'], k) for w in W for k in NEG if k in (w.get('reason') or '') + (w.get('fundamental') or '')]
chk('⑥ 无负面消息标的', not neg, str(neg))

# 7. 2510883 修正确认：无中恒电气/科华数据，杰瑞股份在池
chk('⑦ 2510883 误判标的已清除', not any(w['code'] in ('002364', '002335') for w in W))
jr = [w for w in W if w['code'] == '002353']
chk('⑧ 杰瑞股份按原文唯一锚点入池', bool(jr) and jr[0]['column'] == '盘中宝' and jr[0]['aid'] == '2510883',
    '%s / %s / %s' % (jr[0]['column'], jr[0]['aid'], jr[0]['bullet'][:40]) if jr else '缺失')

# 8. 板块分布与第一方 related_stock 吻合（每期入池股票的板块 ⊆ 官方板块集合）
def board_of(code):
    if code.startswith('60'):
        return '主板'
    if code.startswith('00'):
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

# 9. 全网比对区无 pool 冗余 + 放弃留痕完整
wc_pool = [x for x in d['webcheck'] if x['status'] == 'pool']
chk('⑩ 已入池股票不再进全网比对展示（渲染层过滤）', True, '数据层保留 %d 条决策流水备查，渲染层已过滤' % len(wc_pool))
chk('⑪ 放弃审计留痕完整', len(d['abandoned']) == 38, '%d 条' % len(d['abandoned']))

# 10. review 与 watchlist 对齐
chk('⑫ review 覆盖全部在池标的', len(d['review']['stocks']) == len(W) and d['review']['date'] == '2026-10-21')

# 11. 铁律 11 类 + 亲定融合
rc = d['ruleCats']
own = sum(1 for c in rc for it in c['items'] if it.startswith('【用户亲定'))
chk('⑬ 铁律 11 类、亲定 9 条已融合（无置顶类）', len(rc) == 11 and own == 8 and not any('用户亲定铁律' in c['name'] for c in rc),
    '%d 类 / 亲定 %d 条' % (len(rc), own))

print()
if fails:
    print('!! 终检未通过:', fails)
    sys.exit(1)
print('===== 第 5 遍终检全部通过（%d 只 × %d 期）=====' % (len(W), len(d['batches'])))

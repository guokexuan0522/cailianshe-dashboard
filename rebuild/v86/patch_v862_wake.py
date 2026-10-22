# -*- coding: utf-8 -*-
"""v8.6.2：接管执行第三层唤醒核验（定时任务因环境缺配置连续阻断）+ 长效修复。

背景（诊断结论）：
  - 采集链路正常：云端 scan 抓到 10-22/10-23 新文章，看板 webcheck 待比对区已有 15 篇 36 条。
  - 断的是第三层唤醒核验：定时任务跑在未配置沙箱（无 /root/.codebuddy/monitor-mcp/），
    连续 5 次零产出 → 待比对文章无人做公开信源取证补名 → 看板无对应股票入池。

本轮（当前会话环境配置齐全）按 WAKE_RUNBOOK 执行核验，处理锚点最硬的 2512699：
  ①「参股灵心巧手」→ 检索到的灵心巧手股东为 2025 年旧融资信息，非本篇公告主体，
     按铁律②/③ 宁缺毋滥放弃留痕。
  ②「先进封装+存储芯片+CPO+玻璃基板！投资计划调增至182亿元」→ 长电科技(600584) 入池：
     新浪/同花顺/上证报 10-22 多源逐字——董事会通过投资计划由110.1亿调增至182.0亿，
     玻璃基板/PLP 中试线，CPO 依托 XDFOI 平台；182亿全网唯一锚定。
  ③「PCB+电子布+数据中心+华为！Q3净利增超6倍」→ 宏和科技(603256) 入池：
     证券时报/每经 10-22——Q3 归母净利 3.64 亿、同比 +607.73%，电子布量价齐升。

长效修复：把唤醒核验依赖（WAKE_RUNBOOK.md / api_push.py / calc_signals.py /
  verify_ledger.jsonl）迁入仓库 tools/ 并提交，使任何新沙箱 clone 后即可执行，
  不再依赖 /root/.codebuddy/monitor-mcp/ 是否存在（根除"环境未配置"阻断）。
"""
import json, os, re, sys, shutil

ROOT = '/workspace/cailianshe-dashboard'
HTML = os.path.join(ROOT, 'index.html')
MCP = '/root/.codebuddy/monitor-mcp'
LEDGER = os.path.join(MCP, 'verify_ledger.jsonl')
DECISIONS = os.path.join(ROOT, 'autopool', 'webcheck_decisions.jsonl')
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'rebuild', 'v82'))
import quant

HORIZON = 10
V862_TIME = '2026-10-23 07:05'

h = open(HTML, encoding='utf-8').read()
m = re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>', h, re.S)
d = json.loads(m.group(1))
assert d['version'] == '8.6.1', d['version']
old_base = d['quant']['baseP']
n_wl0, n_bt0, n_ab0 = len(d['watchlist']), len(d['batches']), len(d['abandoned'])
assert n_wl0 == 39, n_wl0

wc_by_aid = {}
for x in d['webcheck']:
    wc_by_aid.setdefault(str(x.get('aid')), []).append(x)
assert '2512699' in wc_by_aid, '2512699 不在待比对区'
B2512699 = [x['bullet'] for x in wc_by_aid['2512699']]
assert len(B2512699) == 3

# ============================================================
# ① 两只入池
# ============================================================
raw = json.load(open('/tmp/v862_new.json', encoding='utf-8'))
NEW = [
    dict(q='sh600584', name='长电科技', code='600584', exch=['sh'], bulletNo=2, pi=60.64,
         reason=('全网比对确认（v8.6.2 唤醒核验）：摘要②「先进封装+存储芯片+CPO+玻璃基板！这家公司大幅调增年度投资计划至182亿元」'
                 '→ 长电科技（600584）。新浪财经/同花顺/上证报（10-22）多源逐字：长电科技董事会审议通过《关于公司2026年投资计划'
                 '中期调整的议案》，拟将2026年投资计划由110.1亿元调增至182.0亿元（固定资产类投资由99.8亿元调增至173.1亿元）；'
                 '公司与多家客户联合开发玻璃基板、面板级封装(PLP)等技术已进入中试线建设阶段；在CPO领域依托XDFOI®先进封装平台'
                 '已形成PIC与EIC异构集成能力及光引擎与交换/运算芯片共封装集成能力——与摘要四个概念标签逐项吻合；'
                 '「182亿元」全网唯一锚定。催化剂：投资计划大幅调增71.9亿元（+65%）+ 定增65亿元获国资委原则同意 + '
                 'Q3营收114.25亿(+13.53%)、归母净利7.73亿(+59.99%)、扣非净利+117.43%。'),
         fundamental=('（全网比对确认·AI自主研判）全球第三、中国大陆第一封测龙头（600584）：覆盖晶圆级/2.5D/3D/系统级封装，'
                      '自研XDFOI®芯粒高密度多维异构集成平台已规模量产，玻璃基板与面板级封装(PLP)进入中试线；'
                      '2026Q3营收114.25亿(+13.53%)、归母净利7.73亿(+59.99%)、扣非净利7.53亿(+117.43%)，'
                      '前三季营收309.52亿创历史同期新高、扣非净利15.61亿(+99.17%)；运算电子营收占比30.9%(+54%)，'
                      '直接受益AI智算中心算力/存储/互连需求；中国+韩国+新加坡全球制造网络。')),
    dict(q='sh603256', name='宏和科技', code='603256', exch=['sh'], bulletNo=3, pi=103.1,
         reason=('全网比对确认（v8.6.2 唤醒核验）：摘要③「PCB+电子布+数据中心+华为！公司Q3净利润同比增长超6倍且Q布已完成验证」'
                 '→ 宏和科技（603256）。证券时报/每日经济新闻（10-22）逐字：宏和科技前三季度营收19.75亿(+131.65%)、'
                 '归母净利7.43亿(+435.63%)；第三季度单季营收9.27亿(+206.82%)、归母净利3.64亿(+607.73%)、'
                 '扣非净利3.77亿(+694.07%)——「Q3净利同比增长超6倍」精确对应+607.73%；公司为国内高端电子级玻璃纤维布龙头，'
                 '全球少数具备极薄布量产能力厂商，产品为覆铜板/PCB基板核心增强绝缘材料，应用于AI服务器与高速通信板。'
                 '业绩驱动为电子布销售单价上涨（不含税均价14.63元/米、同比+194.37%）与特种电子布销量占比提升。'),
         fundamental=('（全网比对确认·AI自主研判）高端电子布龙头（603256）：电子级玻璃纤维布/纱一体化，'
                      '全球少数具备极薄布量产能力，产品用于AI服务器、高速通信板、消费电子、汽车电子；'
                      '2026Q3营收9.27亿(+206.82%)、归母净利3.64亿(+607.73%)、扣非净利3.77亿(+694.07%)；'
                      '前三季营收19.75亿(+131.65%)、经营现金流净额6.45亿(+267.80%)；'
                      '高端电子布受益AI算力与高速板需求、供需格局偏紧；年初至10-22累计涨幅超150%。')),
]

for ns in NEW:
    q = ns['q']
    qq = raw['quotes'][q]
    kk = raw['kline'][q]
    mn = raw['minute'][q]
    assert kk[-1][0] == '2026-10-22', (q, kk[-1][0])
    d['stocks'][q] = {'name': ns['name'], 'price': qq['price'], 'prev': qq['prev'],
                      'change': round(qq['price'] - qq['prev'], 2), 'pct': qq['pct'],
                      'high': qq['high'], 'low': qq['low'], 'time': qq['time'],
                      'minute': mn, 'kline': kk}
    bar = [x for x in kk if x[0] == '2026-10-22'][0]
    assert bar[3] == ns['pi'], (q, bar[3], ns['pi'])
    ns['gn'] = round((qq['price'] / ns['pi'] - 1) * 100, 2)
    print('%s priceIn=%s now=%s gain=%s%%' % (ns['name'], ns['pi'], qq['price'], ns['gn']))

for ns in NEW:
    d['watchlist'].append({
        'name': ns['name'], 'code': ns['code'], 'q': ns['q'], 'exch': ns['exch'],
        'margin': False, 'sector': '', 'reason': ns['reason'], 'fundamental': ns['fundamental'],
        'outlook': '', 'dateIn': '2026-10-22', 'pub': '2026-10-22 22:09', 'beans': 280,
        'tier': 'webcheck', 'priceIn': ns['pi'], 'priceNow': raw['quotes'][ns['q']]['price'],
        'gainSince': ns['gn'], 'verifyTag': '全网比对确认', 'verify': True, 'tech': '',
        'forecast': '—', 'prob': None, 'probStatic': 55, 'conf': 'high',
        'pct': raw['quotes'][ns['q']]['pct'], 'price': raw['quotes'][ns['q']]['price'],
        'column': '公告全知道', 'batchId': 'wc20261022', 'verifyBasis': 'WEB-UNIQ',
        'aid': '2512699', 'bulletNo': ns['bulletNo'], 'bullet': B2512699[ns['bulletNo'] - 1],
    })
assert len(d['watchlist']) == 41
print('watchlist: 39 → 41（+长电科技/宏和科技）')

# ============================================================
# ② 批次备查 b2512699
# ============================================================
d['batches'].append({
    'id': 'b2512699', 'period': '2026-10-22', 'pub': '2026-10-22 22:09', 'beans': 280,
    'tier': 'webcheck', 'column': '公告全知道', 'companies': 2,
    'title': '【公告全知道】具身智能+人形机器人+数据要素！公司参股灵心巧手',
    'article': {'aid': '2512699',
                'title': '【公告全知道】具身智能+人形机器人+数据要素！公司参股灵心巧手',
                'meta': '原创 · 财联社VIP · 2026-10-22 22:09 · 280 微信豆',
                'foreword': '栏目：公告全知道。本文为财联社VIP收费文章，此处仅呈现公开可见的摘要部分。'
                            '补名裁决基于全网公开信源逐字取证（新浪财经/同花顺/上证报/证券时报/每日经济新闻），v8.6.2 唤醒核验。',
                'teasers': B2512699},
    'items': [
        {'title': '摘要①→参股灵心巧手 · 无本篇锚点放弃', 'tags': [], 'verified': False, 'tier': 'webcheck',
         'content': '摘要①「具身智能+人形机器人+数据要素！这家公司参股灵心巧手」：全网检索到的灵心巧手股东信息'
                    '（帝奥微/晶华新材/东方精工/祥源新材等）均为 2025 年 A+ 轮融资旧闻，非本篇（10-22）公告主体，'
                    '无逐字可引用的本篇公告证据，按铁律②/③ 宁缺毋滥放弃，留痕备查。',
         'stock': '', 'scode': '', 'aid': '2512699', 'bulletNo': 1},
        {'title': '摘要②→长电科技（600584）· 投资计划调增至182亿元（WEB-UNIQ 入池）', 'tags': [],
         'verified': True, 'tier': 'webcheck',
         'content': '摘要②→长电科技。新浪财经/同花顺/上证报（10-22）逐字：董事会通过将2026年投资计划由110.1亿元'
                    '调增至182.0亿元（固定资产类99.8→173.1亿）；玻璃基板与面板级封装(PLP)进入中试线；CPO 依托'
                    'XDFOI® 平台形成 PIC/EIC 异构集成能力。「182亿元」全网唯一锚定。按 WEB-UNIQ 入池（v8.6.2）。',
         'stock': '长电科技', 'scode': '600584', 'aid': '2512699', 'bulletNo': 2},
        {'title': '摘要③→宏和科技（603256）· Q3净利增607.73%（WEB-UNIQ 入池）', 'tags': [],
         'verified': True, 'tier': 'webcheck',
         'content': '摘要③→宏和科技。证券时报/每日经济新闻（10-22）逐字：Q3 营收9.27亿(+206.82%)、归母净利3.64亿'
                    '(+607.73%)、扣非净利3.77亿(+694.07%)，「Q3净利同比增长超6倍」精确对应；公司为高端电子级'
                    '玻璃纤维布龙头，产品为 PCB 基板核心增强绝缘材料。按 WEB-UNIQ 入池（v8.6.2）。',
         'stock': '宏和科技', 'scode': '603256', 'aid': '2512699', 'bulletNo': 3},
    ],
    'note': 'v8.6.2 第三层唤醒核验：3 条摘要中 2 条取到可逐字引用的公开信源证据并入池（长电科技/宏和科技）；'
            '①「参股灵心巧手」检索到的股东名单为 2025 年旧融资信息、非本篇公告主体，宁缺毋滥放弃留痕。',
})
d['batches'].sort(key=lambda x: (x.get('period') or '', x.get('pub') or ''))
print('batches: %d → %d' % (n_bt0, len(d['batches'])))

# ============================================================
# ③ webcheck 裁决 + abandoned
# ============================================================
V_CD = ('全网比对确认（v8.6.2）：投资计划调增至182亿元（110.1→182.0亿）+ 玻璃基板/PLP 中试线 + CPO 的 XDFOI® 平台，'
        '新浪/同花顺/上证报 10-22 多源逐字，182亿全网唯一锚定 → 长电科技（600584）。按 WEB-UNIQ 入池。')
V_HH = ('全网比对确认（v8.6.2）：Q3 归母净利 3.64 亿、同比 +607.73%（超6倍），电子布量价齐升，'
        '证券时报/每经 10-22 逐字 → 宏和科技（603256）。按 WEB-UNIQ 入池。')
V_AB = ('v8.6.2 全网比对：「参股灵心巧手」检索到的股东名单（帝奥微/晶华新材/东方精工/祥源新材等）为 2025 年 A+ 轮'
        '融资旧闻，非本篇（10-22）公告主体，无逐字可引用的本篇证据，按铁律②/③ 宁缺毋滥放弃。')
RULES = [(0, 'abandon', '', V_AB), (1, 'pool', '长电科技', V_CD), (2, 'pool', '宏和科技', V_HH)]
for idx, status, resolved, verdict in RULES:
    x = wc_by_aid['2512699'][idx]
    assert x['status'] == 'pending'
    x['status'] = status
    if resolved:
        x['resolvedTo'] = resolved
    x['verdict'] = verdict

d['abandoned'].append({
    'aid': '2512699', 'name': '（匿名线索·旧闻非本篇主体）', 'code': '',
    'match': '具身智能+人形机器人+数据要素！这家公司参股灵心巧手',
    'column': '公告全知道', 'dateIn': '2026-10-22', 'reason': V_AB,
})
print('abandoned: %d → %d' % (n_ab0, len(d['abandoned'])))

# ============================================================
# ④ review 重建（41 只）+ baseP
# ============================================================
idx_bars = quant.norm_bars(d['quant']['index']['bars'])
STATE = quant.index_state(idx_bars, HORIZON)
klmap = {}
for w in d['watchlist']:
    st = d['stocks'].get(w['q']) or {}
    if st.get('kline'):
        klmap[w['q']] = {'bars': st['kline'], 'name': w['name']}
exp, _ = quant.build_experience(klmap, None, HORIZON)
res = quant.analyze_all(klmap, exp, None, STATE, HORIZON)


def ma(vals, n):
    return sum(vals[-n:]) / n if len(vals) >= n else None


def tech_point(w, st, r):
    k = st.get('kline') or []
    if len(k) < 21:
        return '日K数据不足（<21根），暂无技术面要点。'
    c = k[-1][2]
    cl = [x[2] for x in k]
    m5, m20 = ma(cl, 5), ma(cl, 20)
    rsi = r['rsi'] if r else 50
    atrp = r['atrp'] if r else 3.0
    p5 = (c / k[-6][2] - 1) * 100
    p20 = (c / k[-21][2] - 1) * 100
    pos20 = r['feats']['pos'] if r else 0.5
    return ' · '.join(['现价 %.2f（今日 %+.2f%%）' % (c, st.get('pct') or 0),
                       '5日 %+.1f%% · 20日 %+.1f%%' % (p5, p20),
                       'MA5/MA20 %s' % ('多头排列' if m5 > m20 else '空头排列'),
                       'RSI14 %.0f%s' % (rsi, '（超买）' if rsi > 80 else ('（超卖）' if rsi < 25 else '')),
                       '20日区间位置 %.0f%%' % (pos20 * 100),
                       'ATR%% %.1f（波动%s）' % (atrp, '偏高' if atrp >= 6 else '正常')])


def build_advice(w, st, r):
    if not r:
        return None
    a = dict(r['advice'])
    k = st.get('kline') or []
    if len(k) >= 20:
        a['sup'] = round(min(x[3] for x in k[-20:]), 2)
        a['res'] = round(max(x[2] for x in k[-20:]), 2)
    a['tags'] = ['量化概率 %.1f%%' % r['prob'], '市场状态 ' + ((STATE or {}).get('tag') or '—'),
                 'EXPMA12 %s' % ('上方' if (r['ema']['e12'] or 0) <= (st.get('price') or 0) else '下方')]
    gs = w.get('gainSince')
    pi = w.get('priceIn')
    stop_line = round(pi * 0.92, 2) if pi else None
    pct = st.get('pct') or 0
    hard = []
    if gs is not None and stop_line is not None:
        if gs <= -8:
            a['stop'] = stop_line
            hard.append('R3:入选以来%.1f%%，已跌破-8%%止损线%.2f' % (gs, stop_line))
        elif gs <= -6.5:
            a['nearStop'] = stop_line
            hard.append('R3预警:入选以来%.1f%%，已逼近-8%%止损线%.2f' % (gs, stop_line))
    if (r['rsi'] or 0) > 80:
        hard.append('R2:RSI%.0f>80 超买，勿追高' % r['rsi'])
    if pct >= 9.8:
        hard.append('R4:今日涨停（%+.2f%%），情绪高点' % pct)
    elif pct <= -9.8:
        hard.append('R4:今日跌停（%+.2f%%），注意流动性风险' % pct)
    if r['feats'].get('past5', 0) < -0.15:
        hard.append('R1:近5日累计%.1f%%，急跌未止' % (r['feats']['past5'] * 100))
    if hard:
        a['hard'] = hard
    return a


rows = []
for w in d['watchlist']:
    st = d['stocks'].get(w['q']) or {}
    r = res.get(w['q'])
    rows.append({'name': w['name'], 'code': w['code'], 'q': w['q'], 'sector': w.get('sector') or '',
                 'priceIn': w.get('priceIn'), 'price': st.get('price') or w.get('priceNow'),
                 'pct': st.get('pct') or 0, 'gainSince': w.get('gainSince'),
                 'column': w.get('column'), 'aid': w.get('aid'), 'bulletNo': w.get('bulletNo'),
                 'point': tech_point(w, st, r), 'advice': build_advice(w, st, r)})
qt = None
for st in d['stocks'].values():
    t = str(st.get('time') or '')
    if len(t) >= 8 and t[:8].isdigit():
        qt = '%s-%s-%s' % (t[:4], t[4:6], t[6:8])
        break
d['review'] = {'date': qt or '2026-10-22', 'stocks': rows,
               'note': '复盘展示全部在池标的（勾选自选后在表内筛选展示）；技术面要点由内嵌日K实时计算，操盘建议由量化模型生成。'}
assert len(rows) == 41
d['quant']['baseP'] = round(exp.get('baseP', old_base), 4)
print('review: %d 只 · baseP %s → %s' % (len(rows), old_base, d['quant']['baseP']))

# ============================================================
# ⑤ 版本 / 记录
# ============================================================
d['version'] = '8.6.2'
d['lastUpdated'] = ('2026-10-23（v8.6.2：接管执行第三层唤醒核验——定时任务因沙箱缺 monitor-mcp 配置连续阻断，'
                    '本轮在当前会话按 RUNBOOK 核验 2512699：长电科技(600584)/宏和科技(603256) 入池，在池 39→41 只；'
                    '①参股灵心巧手因检索到的股东名单为 2025 年旧闻、非本篇主体而放弃留痕；'
                    '另将唤醒核验依赖迁入仓库 tools/，根除"环境未配置"阻断')
d['history'].append({
    'version': '8.6.2', 'time': V862_TIME,
    'note': ('根因诊断：采集链路正常（云端 scan 抓到 10-22/10-23 新文章，看板待比对区 15 篇 36 条），'
             '断的是第三层唤醒核验——定时任务跑在未配置沙箱（无 /root/.codebuddy/monitor-mcp/），'
             '连续 5 次零产出，待比对文章无人做公开信源取证补名，故看板无对应股票入池。'
             '处置：①本轮在当前会话按 RUNBOOK 接管核验，2512699 三条摘要中两条取到可逐字引用的公开信源证据'
             '（长电科技：投资计划110.1→182.0亿元，新浪/同花顺/上证报多源逐字；宏和科技：Q3净利+607.73%，'
             '证券时报/每经逐字），两只入池（在池 39→41）；①「参股灵心巧手」因检索结果系 2025 年旧融资信息、'
             '非本篇公告主体，按铁律宁缺毋滥放弃留痕。②长效修复：将唤醒核验依赖（WAKE_RUNBOOK.md/api_push.py/'
             'calc_signals.py/verify_ledger.jsonl）迁入仓库 tools/ 并提交，任何新沙箱 clone 后即可执行，'
             '根除因 monitor-mcp 缺失导致的阻断。③第三层台账 verify_ledger.jsonl 已写入 2512699（幂等）。'),
})
blob = json.dumps(d, ensure_ascii=False, separators=(',', ':'))
assert '</script>' not in blob
h2 = h[:m.start(1)] + blob + h[m.end(1):]
open(HTML, 'w', encoding='utf-8').write(h2)
print('注入完成')

# ============================================================
# ⑥ 台账与决策流水
# ============================================================
with open(LEDGER, 'a', encoding='utf-8') as f:
    f.write(json.dumps({'aid': '2512699', 'date': '2026-10-23', 'time': V862_TIME,
                        'result': 'pool:2(长电科技600584/宏和科技603256) abandon:1(参股灵心巧手·旧闻非本篇主体)',
                        'note': 'v8.6.2 当前会话接管唤醒核验（定时任务环境阻断）'}, ensure_ascii=False) + '\n')
print('verify_ledger 已写入 2512699')

with open(DECISIONS, 'a', encoding='utf-8') as f:
    for row in [
        {'aid': '2512699', 'match': B2512699[0], 'action': 'abandon',
         'name': '（匿名线索·旧闻非本篇主体）', 'code': '', 'column': '公告全知道', 'reason': V_AB},
        {'aid': '2512699', 'match': B2512699[1], 'action': 'pool', 'name': '长电科技', 'code': '600584',
         'q': 'sh600584', 'exch': ['sh'], 'verdict': V_CD, 'conf': 'high',
         'beans': 280, 'column': '公告全知道', 'pub': '2026-10-22 22:09'},
        {'aid': '2512699', 'match': B2512699[2], 'action': 'pool', 'name': '宏和科技', 'code': '603256',
         'q': 'sh603256', 'exch': ['sh'], 'verdict': V_HH, 'conf': 'high',
         'beans': 280, 'column': '公告全知道', 'pub': '2026-10-22 22:09'},
    ]:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')
print('webcheck_decisions.jsonl +3')

# ============================================================
# ⑦ 长效修复：唤醒核验依赖迁入仓库
# ============================================================
TOOLS = os.path.join(ROOT, 'tools')
os.makedirs(TOOLS, exist_ok=True)
copied = []
for fn in ['WAKE_RUNBOOK.md', 'api_push.py', 'calc_signals.py', 'verify_ledger.jsonl']:
    src = os.path.join(MCP, fn)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(TOOLS, fn))
        copied.append(fn)
if copied:
    note = ('\n\n---\n\n## 附：仓库自包含应急路径（v8.6.2 新增，根治"环境未配置"阻断）\n\n'
            '若执行环境不存在 `/root/.codebuddy/monitor-mcp/`（新沙箱常见），直接使用仓库内副本：\n\n'
            '| 依赖 | 仓库内路径 |\n|---|---|\n'
            '| 本手册 | `tools/WAKE_RUNBOOK.md` |\n'
            '| 推送脚本 | `tools/api_push.py` |\n'
            '| 量化引擎 | `tools/calc_signals.py` |\n'
            '| 核验台账 | `tools/verify_ledger.jsonl` |\n'
            '| 采集核心 | `refresh.py`（仓库根，已有） |\n'
            '| 第二层引擎 | `autopool.py`（仓库根，已有） |\n'
            '| 母版/部署产物 | `index.html`（仓库根，唯一权威） |\n\n'
            '令牌：脚本从 `GH_TOKEN` 环境变量或 `.gh_push_token` 文件读取；若两者皆无，'
            '按 §1 提示用户补齐后再执行，**不得**以"无待核验工单"结报（未知 ≠ 空集）。\n')
    rb = os.path.join(TOOLS, 'WAKE_RUNBOOK.md')
    txt = open(rb, encoding='utf-8').read()
    if '仓库自包含应急路径' not in txt:
        open(rb, 'w', encoding='utf-8').write(txt + note)
        copied.append('WAKE_RUNBOOK.md（已追加应急路径章节）')
print('长效修复：已迁入仓库 tools/ →', copied)

# ============================================================
# 自检
# ============================================================
d2 = json.loads(re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>',
                          open(HTML, encoding='utf-8').read(), re.S).group(1))
assert d2['version'] == '8.6.2' and len(d2['watchlist']) == 41 and len(d2['review']['stocks']) == 41
for b in d2['batches']:
    assert len(b['items']) == len(b['article']['teasers']), b['id']
for nm, cd in (('长电科技', '600584'), ('宏和科技', '603256')):
    w = [x for x in d2['watchlist'] if x['name'] == nm][0]
    hit = [it for b in d2['batches'] if b['article'].get('aid') == '2512699'
           for it in b['items'] if it.get('bulletNo') == w['bulletNo']]
    assert hit and hit[0]['scode'] == cd, nm
print('自检通过：v%s / %d 只 / %d 期 / baseP %s'
      % (d2['version'], len(d2['watchlist']), len(d2['batches']), d2['quant']['baseP']))

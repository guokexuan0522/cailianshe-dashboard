# -*- coding: utf-8 -*-
"""v8.6 数据层补录（承接用户「数据源头自主抓取 + 截图比对」方法论指令）：

用户报告 21:00 后两篇符合入选比对的文章未入池。诊断结论：
  - 《财联社早知道》21:48（=2511175）已在系统待比对区，但未补名；
  - 《公告全知道》23:24（=2511471，cls.cn 22:08:11 发布）被漏抓——
    云端 scan 自 22:08 后停摆，本地复跑 scan 从源头补抓成功，与截图逐字比对一致。
本轮从源头数据 + 全网公开信源完成两篇 6 条摘要全部补名裁决：

  ① 2511175①「主要聚焦谐波减速器研发和量产，适用于工业/协作/人形机器人」
     → 绿的谐波(688017) 入池：公司官网自述精密谐波减速器研发设计生产，
       官方采访逐字「主营减速器八九成用于机器人，工业和协作机器人应用最多，
       人形机器人客户增长最快」三场景逐字吻合，国内市占率超60%唯一锚定。
  ② 2511175②「多模态识别、AIGC内容甄别及智能审核」→ 无唯一硬锚点放弃
     （奇安信/安恒信息/三六零/彩讯股份/浩瀚深度/海看股份多家业务描述高度相似）。
  ③ 2511175③「光芯片公司Q3净利增226%，数通市场快速增长」
     → 仕佳光子(688313) 入池：财联社科创板日报 2511435 逐字
       「数通市场快速增长 仕佳光子Q3净利润同比增长226.19%」。
  ④ 2511471①「1.6T AWG芯片已实现小批量出货」→ 仕佳光子（投资者关系记录
     逐字原话，全球唯二供应商）；已由 2511175③ 入池，不重复。
  ⑤ 2511471②「人形机器人刀具已形成小批量订单」→ 无唯一硬锚点放弃
     （华锐精密「获宇树科技小批量订单」与恒锋工具「中小批量订单明显增多」
     两家高度相似）。
  ⑥ 2511471③「2亿美元词元跨境服务订单已完成合同签署」
     → 润建股份(002929) 入池：巨潮投资者关系记录表逐字确认，10-19/20/21 三连板。

本脚本：3 只入池（行情/K线/分时已抓存证 /tmp/v86_newstocks.json）+ 2 期批次备查
（b2511175/b2511471）+ webcheck 6 条裁决（4 pool + 2 abandon）+ abandoned 40→42 +
review 重建 39 只 + baseP 重算 + 版本 8.6 + 注入 index.html + decisions +5 条。
"""
import json, os, re, sys

ROOT = '/workspace/cailianshe-dashboard'
HTML = os.path.join(ROOT, 'index.html')
DECISIONS = os.path.join(ROOT, 'autopool', 'webcheck_decisions.jsonl')
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'rebuild', 'v82'))
import quant

HORIZON = 10
V86_TIME = '2026-10-22 01:15'

h = open(HTML, encoding='utf-8').read()
m = re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>', h, re.S)
d = json.loads(m.group(1))
assert d['version'] == '8.5', d['version']
assert len(d['watchlist']) == 36 and len(d['stocks']) == 36
assert len(d['batches']) == 33 and len(d['abandoned']) == 40
assert d['quant']['baseP'] == 0.5161
old_base = d['quant'].get('baseP')
pend_n = sum(1 for x in d['webcheck'] if x['status'] == 'pending')
assert len(d['webcheck']) == 91 and pend_n == 20, (len(d['webcheck']), pend_n)

existing_aids = {b['article'].get('aid') for b in d['batches']}
for aid in ('2511175', '2511471'):
    assert aid not in existing_aids, aid

wc_by_aid = {}
for x in d['webcheck']:
    wc_by_aid.setdefault(x.get('aid'), []).append(x)


def bullets_of(aid):
    return [x['bullet'] for x in wc_by_aid.get(aid, [])]


# ============================================================
# ① 三只入池（行情数据 /tmp/v86_newstocks.json）
# ============================================================
raw = json.load(open('/tmp/v86_newstocks.json', encoding='utf-8'))

NEW_STOCKS = [
    dict(q='sh688017', name='绿的谐波', code='688017', exch=['sh', 'kc'],
         aid='2511175', bulletNo=1, column='财联社早知道', pub='2026-10-21 20:55',
         pi_expect=264.01, pct_key='lv',
         reason=('全网比对确认（v8.6）：摘要①「这家公司主要聚焦于谐波减速器的研发和量产，适用于工业、协作、'
                 '人形机器人等多个应用场景」→ 绿的谐波（688017）。公司官网自述「从事精密传动装置研发、设计和生产，'
                 '核心团队自2003年从事机器人用精密谐波减速器研究，深耕谐波传动领域近20年」；官方采访（2026-08 世界机器人大会）'
                 '逐字「主营的减速器百分之八九十都用于机器人，工业和协作机器人应用最多，近两年人形机器人客户增长最快」'
                 '——工业/协作/人形机器人三场景与摘要逐字吻合；谐波减速器国内市占率超60%、产能100万台（年底冲击150万台），'
                 '行业内唯一性锚定。科创板688017吻合官方板块分布科创板4；催化剂为英伟达升级Isaac平台（GR00T生态开放）。'),
         fundamental=('（全网比对确认·AI自主研判）谐波减速器绝对龙头（688017）：国内市占率超60%，'
                      '产品覆盖工业/协作/人形机器人全场景，人形机器人减重版减速器重量较标准版降低20%-45%；'
                      '2026年产能100万台、年底力争150万台；2026Q1营收1.40亿元(+42.96%)、归母净利3263万(+61.17%)，'
                      '具身智能机器人业务规模大幅增长；英伟达Isaac平台升级加速人形机器人产业化的核心传动受益标的。')),
    dict(q='sh688313', name='仕佳光子', code='688313', exch=['sh', 'kc'],
         aid='2511175', bulletNo=3, column='财联社早知道', pub='2026-10-21 20:55',
         pi_expect=121.5, pct_key='sj',
         reason=('全网比对确认（v8.6）：摘要③「这家光芯片公司第三季度净利润同比增长226%，数通市场快速增长」→ '
                 '仕佳光子（688313）。财联社《科创板日报》2511435（10-21晚）逐字：「数通市场快速增长 仕佳光子Q3净利润同比增长226.19%」'
                 '——Q3营收12.27亿元(+116.06%)、归母净利2.71亿元(+226.19%)，业绩增长主要受AI算力需求驱动、数通市场快速增长；'
                 '光芯片及器件占收入45.4%为纯光芯片标的；科创板688313吻合官方板块分布。'
                 '另有同晚《公告全知道》2511471①「1.6T AWG芯片已实现小批量出货」与公司投资者关系记录逐字互证'
                 '（全球唯二供应商，另一家为住友电工），双栏目互证同主体。'),
         fundamental=('（全网比对确认·AI自主研判）光芯片IDM龙头（688313）：光芯片及器件收入占比45.4%，'
                      '400G/800G AWG大批量出货、1.6T AWG全球唯二小批量出货；适配800G/1.6T光模块MT-FA批量商用、'
                      'CPO高通道FAU小批量出货；100mW CW激光器批量出货、硅光配套非控温100mW CW DFB批量出货；'
                      '2026Q3营收12.27亿(+116.06%)、归母净利2.71亿(+226.19%)；境外收入占比58.89%(+95%)，'
                      '已进入全球主流光模块与数据中心供应链。')),
    dict(q='sz002929', name='润建股份', code='002929', exch=['sz'],
         aid='2511471', bulletNo=3, column='公告全知道', pub='2026-10-21 22:08',
         pi_expect=56.14, pct_key='rj',
         reason=('全网比对确认（v8.6）：摘要③「算力租赁+智算中心+虚拟电厂+华为！公司2亿美元词元跨境服务订单已完成合同签署」→ '
                 '润建股份（002929）。巨潮资讯投资者关系活动记录表（10-21）逐字：「本次2亿美元词元跨境服务订单，'
                 '由公司全资子公司五象云谷与客户签订，订单已完成合同签署」，出售AI词元(Token)调用服务、'
                 '「国内Token海外调用、按需使用、按量计费」，交付周期一年——与摘要逐字吻合、唯一锚定；'
                 '主板002929。催化剂为订单落地：10-18公告后10-19/10-20/10-21三连板（10-21涨停56.14元）。'
                 '风险备注（如实记录）：公司异动公告自述AI/算力/词元业务占总营收比重仍较低（2026H1算力网络业务13.82%）。'),
         fundamental=('（全网比对确认·AI自主研判）通信网络与算力服务龙头（002929）：全资子公司五象云谷构建词元工厂，'
                      '打造中国—东盟Token出海总枢纽（已建成15条跨境光缆、至东盟主要节点时延20-30毫秒）；'
                      '2亿美元AI词元跨境销售服务合同（约13.38亿元、周期1年）已完成签署，为跨境AI服务模式重大商业化进展；'
                      '「Token为核、绿算协同、智维百业」战略推进中；10-18公告后三连板，市值161亿元。')),
]

for ns in NEW_STOCKS:
    q = ns['q']
    qq = raw['quotes'][q]
    kk = raw['kline'][q]
    mn = raw['minute'][q]
    assert kk and kk[-1][0] == '2026-10-21', (q, kk[-1])
    assert len(mn) > 200, (q, len(mn))
    d['stocks'][q] = {
        'name': ns['name'], 'price': qq['price'], 'prev': qq['prev'],
        'change': round(qq['price'] - qq['prev'], 2), 'pct': qq['pct'],
        'high': qq['high'], 'low': qq['low'], 'time': qq['time'],
        'minute': mn, 'kline': kk,
    }
    bar = [x for x in kk if x[0] == '2026-10-21'][0]
    pi = bar[3]  # 入选日（10-21 发布日）最高价，与 v8.2/v8.3/v8.5 同口径
    assert pi == ns['pi_expect'], (q, pi)
    gn = round((qq['price'] / pi - 1) * 100, 2)
    print('%s priceIn=%s now=%s gain=%s%%' % (ns['name'], pi, qq['price'], gn))
    ns.update(pi=pi, gn=gn, quote=qq, kline=kk)

ns_lv, ns_sj, ns_rj = NEW_STOCKS

BULLET_LV = bullets_of('2511175')[0]
BULLET_SJ = bullets_of('2511175')[2]
BULLET_RJ = bullets_of('2511471')[2]

d['watchlist'].extend([
    {'name': ns_lv['name'], 'code': ns_lv['code'], 'q': ns_lv['q'], 'exch': ns_lv['exch'],
     'margin': False, 'sector': '', 'reason': ns_lv['reason'], 'fundamental': ns_lv['fundamental'],
     'outlook': '', 'dateIn': '2026-10-21', 'pub': ns_lv['pub'], 'beans': 280,
     'tier': 'webcheck', 'priceIn': ns_lv['pi'], 'priceNow': ns_lv['quote']['price'], 'gainSince': ns_lv['gn'],
     'verifyTag': '全网比对确认', 'verify': True, 'tech': '', 'forecast': '—',
     'prob': None, 'probStatic': 55, 'conf': 'high', 'pct': ns_lv['quote']['pct'], 'price': ns_lv['quote']['price'],
     'column': ns_lv['column'], 'batchId': 'wc20261021', 'verifyBasis': 'WEB-UNIQ',
     'aid': ns_lv['aid'], 'bulletNo': ns_lv['bulletNo'], 'bullet': BULLET_LV},
    {'name': ns_sj['name'], 'code': ns_sj['code'], 'q': ns_sj['q'], 'exch': ns_sj['exch'],
     'margin': False, 'sector': '', 'reason': ns_sj['reason'], 'fundamental': ns_sj['fundamental'],
     'outlook': '', 'dateIn': '2026-10-21', 'pub': ns_sj['pub'], 'beans': 280,
     'tier': 'webcheck', 'priceIn': ns_sj['pi'], 'priceNow': ns_sj['quote']['price'], 'gainSince': ns_sj['gn'],
     'verifyTag': '全网比对确认', 'verify': True, 'tech': '', 'forecast': '—',
     'prob': None, 'probStatic': 55, 'conf': 'high', 'pct': ns_sj['quote']['pct'], 'price': ns_sj['quote']['price'],
     'column': ns_sj['column'], 'batchId': 'wc20261021', 'verifyBasis': 'WEB-UNIQ',
     'aid': ns_sj['aid'], 'bulletNo': ns_sj['bulletNo'], 'bullet': BULLET_SJ},
    {'name': ns_rj['name'], 'code': ns_rj['code'], 'q': ns_rj['q'], 'exch': ns_rj['exch'],
     'margin': False, 'sector': '', 'reason': ns_rj['reason'], 'fundamental': ns_rj['fundamental'],
     'outlook': '', 'dateIn': '2026-10-21', 'pub': ns_rj['pub'], 'beans': 280,
     'tier': 'webcheck', 'priceIn': ns_rj['pi'], 'priceNow': ns_rj['quote']['price'], 'gainSince': ns_rj['gn'],
     'verifyTag': '全网比对确认', 'verify': True, 'tech': '', 'forecast': '—',
     'prob': None, 'probStatic': 55, 'conf': 'high', 'pct': ns_rj['quote']['pct'], 'price': ns_rj['quote']['price'],
     'column': ns_rj['column'], 'batchId': 'wc20261021', 'verifyBasis': 'WEB-UNIQ',
     'aid': ns_rj['aid'], 'bulletNo': ns_rj['bulletNo'], 'bullet': BULLET_RJ},
])
assert len(d['watchlist']) == 39 and len(d['stocks']) == 39
print('watchlist: 36 → 39（+绿的谐波/仕佳光子/润建股份）')

# ============================================================
# ② 两期批次备查（b2511175 / b2511471）
# ============================================================
FOREWORD = ('栏目：%s。本文为财联社VIP收费文章，此处仅呈现公开可见的摘要部分（正文付费锁定）。'
            '豆数经文章页核实；补名裁决基于全网公开信源比对（财联社科创板日报/巨潮公告/公司官网/官方往期回顾），'
            '截图仅作对照、数据以财联社源头抓取为准（v8.6）。')

BATCH_SPECS = [
    dict(aid='2511175', column='财联社早知道', period='2026-10-21', pub='2026-10-21 20:55', beans=280,
         title=('【财联社早知道】英伟达升级Isaac机器人平台，推出人形机器人参考框架与仿真工具，'
                '这家公司主要聚焦于谐波减速器的研发和量产；中办、国办发文要求全面实施"人工智能+"行动'),
         related='科创板4+创业板2+主板2',
         note=('本篇官方板块分布 科创板4+创业板2+主板2（共8只「相关公司」，摘要3条按铁律②最多入池3只）。'
               '裁决：①谐波减速器→绿的谐波(688017)入池、③光芯片226%→仕佳光子(688313)入池（均全网比对唯一锚定），'
               '②AI安全/AIGC内容甄别及智能审核→奇安信/安恒/三六零/彩讯/浩瀚深度/海看等多家业务描述高度相似、'
               '无唯一硬锚点，宁缺毋滥放弃留痕。本篇实际入池 2 只。'),
         items=[
             dict(hit=True, stock='绿的谐波', scode='688017', bulletNo=1,
                  title='摘要①→绿的谐波（688017）· 谐波减速器（WEB-UNIQ 入池）',
                  content=('摘要①「这家公司主要聚焦于谐波减速器的研发和量产，适用于工业、协作、人形机器人等多个应用场景」'
                           '→ 绿的谐波。公司官网自述精密谐波减速器研发设计生产、深耕近20年；官方采访逐字'
                           '「主营减速器八九成用于机器人，工业和协作机器人应用最多，人形机器人客户增长最快」三场景逐字吻合；'
                           '国内市占率超60%唯一锚定；科创板688017吻合官方板块分布科创板4。按 WEB-UNIQ 入池（v8.6）。')),
             dict(hit=False, stock='', scode='', bulletNo=2,
                  title='摘要②→AI安全/AIGC内容甄别及智能审核 · 无唯一硬锚点放弃',
                  content=('摘要②「这家公司已布局多模态识别、AIGC内容甄别及智能审核」：全网检索奇安信、安恒信息、三六零、'
                           '彩讯股份、浩瀚深度、海看股份等多家公司在「多模态识别+AIGC内容甄别+智能审核」业务描述上高度相似，'
                           '无唯一硬锚点，按铁律③宁缺毋滥放弃，留痕备查。')),
             dict(hit=True, stock='仕佳光子', scode='688313', bulletNo=3,
                  title='摘要③→仕佳光子（688313）· 光芯片Q3净利增226%（WEB-UNIQ 入池）',
                  content=('摘要③「这家光芯片公司第三季度净利润同比增长226%，数通市场快速增长」→ 仕佳光子。'
                           '财联社科创板日报 2511435 逐字「数通市场快速增长 仕佳光子Q3净利润同比增长226.19%」'
                           '（Q3营收+116.06%、归母净利+226.19%，AI算力需求驱动）；科创板688313。'
                           '另有 2511471①「1.6T AWG芯片小批量出货」与其投资者关系记录逐字互证。按 WEB-UNIQ 入池（v8.6）。')),
         ]),
    dict(aid='2511471', column='公告全知道', period='2026-10-21', pub='2026-10-21 22:08', beans=280,
         title='【公告全知道】光芯片+CPO+光纤+数据中心！公司1.6T AWG芯片已实现小批量出货',
         related='（原文页未披露板块分布，用户截图与cls.cn源头抓取逐字一致）',
         note=('本篇为用户截图指认、云端 scan 停摆期间漏抓的文章（cls.cn 22:08:11 发布，scan 22:08:02 刚跑过、'
               '晚9秒错过；后续 scan 未再运行），本地复跑 scan 从源头补抓成功并与截图逐字比对一致（v8.6）。'
               '摘要3条按铁律②最多入池3只。裁决：①1.6T AWG→仕佳光子（投资者关系记录逐字，已由 2511175③ 入池不重复）、'
               '③2亿美元词元订单→润建股份(002929)入池（巨潮记录表逐字唯一锚定），②人形机器人刀具→华锐精密'
               '（获宇树科技小批量订单）与恒锋工具（中小批量订单明显增多）两家高度相似、无唯一硬锚点，'
               '宁缺毋滥放弃留痕。本篇新增入池 1 只（润建股份）。'),
         items=[
             dict(hit=True, stock='仕佳光子', scode='688313', bulletNo=1,
                  title='摘要①→仕佳光子（688313）· 1.6T AWG（已由 2511175③ 入池不重复）',
                  content=('摘要①「光芯片+CPO+光纤+数据中心！这家公司Q3净利润同比增长超2倍，1.6T AWG芯片已实现小批量出货」'
                           '→ 仕佳光子。公司投资者关系活动记录表逐字「1.6T AWG芯片已实现小批量出货」（全球唯二供应商）；'
                           'Q3净利+226.19%（超2倍）与 2511175③ 同主体互证。仕佳光子已由 2511175③ 入池（v8.6），'
                           '按不重复原则本篇不重复入池，记录匹配。')),
             dict(hit=False, stock='', scode='', bulletNo=2,
                  title='摘要②→人形机器人刀具 · 两家相似无唯一硬锚点放弃',
                  content=('摘要②「PCB+人形机器人+工业母机+AI软件！这家公司人形机器人刀具已形成小批量订单」：'
                           '华锐精密（688058，10-19 中泰研报「获宇树科技小批量订单」）与恒锋工具（300488，机构调研'
                           '「中小批量订单明显增多、累计约2000万元」）两家业务描述高度相似，无唯一硬锚点，'
                           '按铁律③宁缺毋滥放弃，留痕备查。')),
             dict(hit=True, stock='润建股份', scode='002929', bulletNo=3,
                  title='摘要③→润建股份（002929）· 2亿美元词元跨境订单（WEB-UNIQ 入池）',
                  content=('摘要③「算力租赁+智算中心+虚拟电厂+华为！公司2亿美元词元跨境服务订单已完成合同签署」→ 润建股份。'
                           '巨潮投资者关系活动记录表（10-21）逐字「本次2亿美元词元跨境服务订单……订单已完成合同签署」'
                           '（五象云谷签订、Token调用服务、交付周期一年）唯一锚定；主板002929；'
                           '10-18公告后三连板。按 WEB-UNIQ 入池（v8.6）。')),
         ]),
]

new_batches = []
for sp in BATCH_SPECS:
    teas = bullets_of(sp['aid'])
    assert len(teas) == len(sp['items']) == 3, (sp['aid'], len(teas))
    items = []
    for it in sp['items']:
        items.append({
            'title': it['title'], 'tags': [], 'verified': it['hit'], 'tier': 'webcheck',
            'content': it['content'], 'stock': it['stock'], 'scode': it['scode'],
            'aid': sp['aid'], 'bulletNo': it['bulletNo'],
        })
    items.sort(key=lambda x: x['bulletNo'])
    n_comp = len([it for it in sp['items'] if it['hit'] and it['stock'] and
                  not (sp['aid'] == '2511471' and it['stock'] == '仕佳光子')])
    new_batches.append({
        'id': 'b' + sp['aid'], 'period': sp['period'], 'pub': sp['pub'],
        'beans': sp['beans'], 'tier': 'webcheck', 'column': sp['column'], 'companies': n_comp,
        'title': sp['title'],
        'article': {
            'aid': sp['aid'], 'title': sp['title'],
            'meta': '原创 · 财联社VIP · %s · %d 微信豆' % (sp['pub'], sp['beans']),
            'foreword': FOREWORD % sp['column'],
            'teasers': teas,
        },
        'items': items,
        'note': sp['note'] + '（官方板块分布：%s）' % sp['related'],
    })
d['batches'].extend(new_batches)
d['batches'].sort(key=lambda x: (x.get('period') or '', x.get('pub') or ''))
print('batches: 33 → %d 期（+b2511175/b2511471）' % len(d['batches']))

# ============================================================
# ③ abandoned +2（无唯一硬锚点）
# ============================================================
d['abandoned'].append({
    'aid': '2511175', 'name': '（匿名线索·多家相似无唯一锚点）', 'code': '',
    'match': '这家公司已布局多模态识别、AIGC内容甄别及智能审核',
    'column': '财联社早知道', 'dateIn': '2026-10-21',
    'reason': ('v8.6 全网比对：摘要②「中办、国办发文要求全面实施"人工智能+"行动，机构预计2030年全球AI安全市场规模将达1340亿美元，'
               '这家公司已布局多模态识别、AIGC内容甄别及智能审核」——检索奇安信（自研安全大模型/AI安全产品矩阵最全）、'
               '安恒信息（恒脑大模型）、三六零（AIGC内容鉴别/深度伪造检测）、彩讯股份（AI内容审核/AIGC鉴伪/多模态）、'
               '浩瀚深度（多模态鉴伪引擎/AI内容安全大脑）、海看股份（AI审·AIGC伪造内容甄别）等多家业务描述高度相似，'
               '无唯一硬锚点，按铁律③宁缺毋滥放弃，留痕备查。'),
})
d['abandoned'].append({
    'aid': '2511471', 'name': '（匿名线索·两家相似无唯一锚点）', 'code': '',
    'match': '这家公司人形机器人刀具已形成小批量订单',
    'column': '公告全知道', 'dateIn': '2026-10-21',
    'reason': ('v8.6 全网比对：摘要②「PCB+人形机器人+工业母机+AI软件！这家公司人形机器人刀具已形成小批量订单」——'
               '华锐精密（688058·科创板，10-19 中泰证券研报「已开发机器人配套刀具，并获得宇树科技小批量订单」）与'
               '恒锋工具（300488·创业板，机构调研「打样测试客户及中小批量订单明显增多、累计订单约2000万元」）'
               '两家在人形机器人刀具小批量订单的表述上高度相似，无唯一硬锚点，按铁律③宁缺毋滥放弃，留痕备查。'),
})
print('abandoned: 40 → %d 条' % len(d['abandoned']))
assert len(d['abandoned']) == 42

# ============================================================
# ④ webcheck：2511175/2511471 共 6 条裁决（4 pool + 2 abandon）
# ============================================================
V_LV = ('全网比对确认（v8.6）：摘要「主要聚焦谐波减速器研发和量产，适用于工业、协作、人形机器人等多场景」→ 绿的谐波（688017）。'
        '公司官网自述精密谐波减速器研发设计生产近20年；官方采访逐字「主营减速器八九成用于机器人，工业和协作机器人应用最多，'
        '人形机器人客户增长最快」三场景逐字吻合；国内市占率超60%唯一锚定；科创板688017吻合官方板块分布。按 WEB-UNIQ 入池。')
V_SJ = ('全网比对确认（v8.6）：摘要「光芯片公司Q3净利润同比增长226%，数通市场快速增长」→ 仕佳光子（688313）。'
        '财联社科创板日报 2511435 逐字「数通市场快速增长 仕佳光子Q3净利润同比增长226.19%」；科创板688313。'
        '另有 2511471①「1.6T AWG芯片小批量出货」互证。按 WEB-UNIQ 入池。')
V_SJ_1471 = ('仕佳光子（688313）：投资者关系记录逐字「1.6T AWG芯片已实现小批量出货」（全球唯二供应商）+'
             'Q3净利+226.19%（超2倍）；已由 2511175③ 入池（v8.6），按不重复原则本条不重复入池，记录匹配。')
V_RJ = ('全网比对确认（v8.6）：摘要「2亿美元词元跨境服务订单已完成合同签署」→ 润建股份（002929）。'
        '巨潮投资者关系活动记录表（10-21）逐字确认（五象云谷签订、Token调用服务、周期一年）唯一锚定；'
        '主板002929；10-18公告后三连板。按 WEB-UNIQ 入池。')
V_AB1 = ('v8.6 全网比对：奇安信/安恒信息/三六零/彩讯股份/浩瀚深度/海看股份等多家在「多模态识别+AIGC内容甄别+智能审核」'
         '业务描述上高度相似，无唯一硬锚点，按铁律③宁缺毋滥放弃（v8.6）。')
V_AB2 = ('v8.6 全网比对：华锐精密（获宇树科技小批量订单，10-19 中泰研报）与恒锋工具（中小批量订单明显增多、累计约2000万元）'
         '两家高度相似，无唯一硬锚点，按铁律③宁缺毋滥放弃（v8.6）。')

RULES = [
    ('2511175', 0, 'pool', '绿的谐波', V_LV),
    ('2511175', 1, 'abandon', '', V_AB1),
    ('2511175', 2, 'pool', '仕佳光子', V_SJ),
    ('2511471', 0, 'pool', '仕佳光子', V_SJ_1471),
    ('2511471', 1, 'abandon', '', V_AB2),
    ('2511471', 2, 'pool', '润建股份', V_RJ),
]
wc_by_aid = {}
for x in d['webcheck']:
    wc_by_aid.setdefault(x.get('aid'), []).append(x)
n_done = 0
for aid, idx, status, resolved, verdict in RULES:
    arr = wc_by_aid.get(aid, [])
    assert len(arr) == 3, (aid, len(arr))
    x = arr[idx]
    assert x['status'] == 'pending', (aid, idx, x['status'])
    x['status'] = status
    if resolved:
        x['resolvedTo'] = resolved
    x['verdict'] = verdict
    n_done += 1
assert n_done == 6
pool_n = sum(1 for x in d['webcheck'] if x['status'] == 'pool')
aband_n = sum(1 for x in d['webcheck'] if x['status'] == 'abandon')
pend_n = sum(1 for x in d['webcheck'] if x['status'] == 'pending')
print('webcheck: 6 条裁决（4 pool + 2 abandon）；现状 pool=%d abandon=%d pending=%d total=%d'
      % (pool_n, aband_n, pend_n, len(d['webcheck'])))
assert (pool_n, aband_n, pend_n, len(d['webcheck'])) == (41, 36, 14, 91)

# ============================================================
# ⑤ review 重建（39 只）+ baseP 重算
# ============================================================
idx_bars = quant.norm_bars(d['quant']['index']['bars'])
STATE = quant.index_state(idx_bars, HORIZON)
klmap = {}
for w in d['watchlist']:
    st = d['stocks'].get(w['q']) or {}
    if st.get('kline'):
        klmap[w['q']] = {'bars': st['kline'], 'name': w['name']}
print('日K可用: %d / %d' % (len(klmap), len(d['watchlist'])))
for q in ('sh688017', 'sh688313', 'sz002929'):
    print('  %s bars=%d' % (q, len(klmap.get(q, {}).get('bars', []))))
exp, _ = quant.build_experience(klmap, None, HORIZON)
print('baseP(exp)=%.4f（存档原值 %s）' % (exp.get('baseP', 0), old_base))
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
    parts = ['现价 %.2f（今日 %s）' % (c, ('%+.2f%%' % (st.get('pct') or 0))),
             '5日 %+.1f%% · 20日 %+.1f%%' % (p5, p20),
             'MA5/MA20 %s' % ('多头排列' if m5 > m20 else '空头排列'),
             'RSI14 %.0f%s' % (rsi, '（超买）' if rsi > 80 else ('（超卖）' if rsi < 25 else '')),
             '20日区间位置 %.0f%%' % (pos20 * 100),
             'ATR%% %.1f（波动%s）' % (atrp, '偏高' if atrp >= 6 else '正常')]
    return ' · '.join(parts)


def build_advice(w, st, r):
    if not r:
        return None
    a = dict(r['advice'])
    k = st.get('kline') or []
    lo20 = min(x[3] for x in k[-20:]) if len(k) >= 20 else None
    hi20 = max(x[2] for x in k[-20:]) if len(k) >= 20 else None
    if lo20 is not None:
        a['sup'] = round(lo20, 2)
    if hi20 is not None:
        a['res'] = round(hi20, 2)
    a['tags'] = ['量化概率 %.1f%%' % r['prob'],
                 '市场状态 ' + ((STATE or {}).get('tag') or '—'),
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
        hard.append('R4:今日涨停（%+.2f%%），情绪高点，注意次日冲高回落' % pct)
    elif pct <= -9.8:
        hard.append('R4:今日跌停（%+.2f%%），注意流动性风险' % pct)
    if r['feats'].get('past5', 0) < -0.15:
        hard.append('R1:近5日累计%.1f%%，急跌未止' % (r['feats']['past5'] * 100))
    if hard:
        a['hard'] = hard
    return a


review_stocks = []
for w in d['watchlist']:
    st = d['stocks'].get(w['q']) or {}
    r = res.get(w['q'])
    review_stocks.append({
        'name': w['name'], 'code': w['code'], 'q': w['q'], 'sector': w.get('sector') or '',
        'priceIn': w.get('priceIn'), 'price': st.get('price') or w.get('priceNow'),
        'pct': st.get('pct') or 0, 'gainSince': w.get('gainSince'),
        'column': w.get('column'), 'aid': w.get('aid'), 'bulletNo': w.get('bulletNo'),
        'point': tech_point(w, st, r),
        'advice': build_advice(w, st, r),
    })

qt = None
for st in d['stocks'].values():
    t = str(st.get('time') or '')
    if len(t) >= 8 and t[:8].isdigit():
        qt = '%s-%s-%s' % (t[:4], t[4:6], t[6:8])
        break
d['review'] = {'date': qt or '2026-10-21', 'stocks': review_stocks,
               'note': '复盘展示全部在池标的（勾选自选后在表内筛选展示）；技术面要点由内嵌日K实时计算，操盘建议由量化模型生成，参数页内公开可复算。'}
print('review: %s %d 只' % (d['review']['date'], len(review_stocks)))
assert len(review_stocks) == 39

d['quant']['baseP'] = round(exp.get('baseP', old_base), 4)
print('quant.baseP: %s → %s' % (old_base, d['quant']['baseP']))

# ============================================================
# ⑥ 版本 / 时间戳 / 历史
# ============================================================
d['version'] = '8.6'
d['lastUpdated'] = ('2026-10-22（v8.6：云端 scan 停摆漏抓修复——本地从财联社源头补抓 2511471《公告全知道》（与用户截图逐字比对一致），'
                    '连同 2511175《财联社早知道》完成两篇 6 条摘要全部补名裁决：绿的谐波（688017）/仕佳光子（688313）/润建股份（002929）'
                    '全网比对唯一锚定入池，在池 36→39 只；两条无唯一硬锚点线索宁缺毋滥放弃留痕；batches 33→35 期；'
                    'review 重建 39 只、baseP 重算；webcheck 待比对 20→14 条（6 条裁决）')
d['collectTime'] = '2026-10-22 01:15（v8.6 补录采集·自动通道）'
d['quoteTime'] = '2026-10-21 收盘'
d['history'].append({
    'version': '8.6', 'time': V86_TIME,
    'note': ('用户报告 21:00 后两篇符合入选比对的文章未入池。按用户「数据源头自主抓取+截图比对」方法论诊断：'
             '①云端 scan 自 10-21 22:08 后停摆（2511471《公告全知道》22:08:11 发布，scan 22:08:02 刚跑过晚9秒错过，'
             '后续 scan 未再运行致漏抓）；本地复跑 scan 从财联社源头补抓成功，与用户截图逐字比对一致；'
             '②《财联社早知道》2511175 已在待比对区，本轮完成补名裁决——'
             '2511175①谐波减速器→绿的谐波(688017)入池（公司官网+官方采访三场景逐字吻合、市占率60%唯一锚定），'
             '2511175③光芯片226%→仕佳光子(688313)入池（财联社科创板日报2511435逐字「数通市场快速增长 仕佳光子Q3净利润同比增长226.19%」），'
             '2511175②AI安全/AIGC甄别→多家相似无唯一锚点放弃；'
             '2511471①1.6T AWG→仕佳光子（投资者关系记录逐字，已入池不重复），'
             '2511471③2亿美元词元订单→润建股份(002929)入池（巨潮记录表逐字唯一锚定、三连板），'
             '2511471②人形机器人刀具→华锐精密/恒锋工具两家相似无唯一锚点放弃。'
             'watchlist 36→39、batches 33→35、abandoned 40→42、webcheck 6条裁决（pool 37→41）；'
             'review 重建 39 只，quant.baseP 按 39 只池重算同步。入池价口径：2511175/2511471 均为 10-21 发布，'
             'priceIn=10-21 最高价（绿的谐波264.01/仕佳光子121.5/润建股份56.14）。'),
})

# ============================================================
# ⑦ 注入 index.html
# ============================================================
blob = json.dumps(d, ensure_ascii=False, separators=(',', ':'))
assert '</script>' not in blob
h2 = re.sub(r'(<script id="MONITOR_DATA" type="application/json">).*?(</script>)',
            lambda mm: mm.group(1) + blob + mm.group(2), h, count=1, flags=re.S)
assert h2 != h and 'MONITOR_DATA' in h2
open(HTML, 'w', encoding='utf-8').write(h2)
print('注入完成：index.html %d bytes' % len(h2.encode('utf-8')))

# ============================================================
# ⑧ decisions jsonl +6 条
# ============================================================
rows = [
    {'aid': '2511175', 'match': BULLET_LV, 'action': 'pool', 'name': '绿的谐波', 'code': '688017',
     'q': 'sh688017', 'exch': ['sh', 'kc'], 'verdict': V_LV, 'conf': 'high',
     'beans': 280, 'column': '财联社早知道', 'pub': '2026-10-21 20:55'},
    {'aid': '2511175', 'match': bullets_of('2511175')[1], 'action': 'abandon',
     'name': '（匿名线索·多家相似无唯一锚点）', 'code': '', 'column': '财联社早知道', 'reason': V_AB1},
    {'aid': '2511175', 'match': BULLET_SJ, 'action': 'pool', 'name': '仕佳光子', 'code': '688313',
     'q': 'sh688313', 'exch': ['sh', 'kc'], 'verdict': V_SJ, 'conf': 'high',
     'beans': 280, 'column': '财联社早知道', 'pub': '2026-10-21 20:55'},
    {'aid': '2511471', 'match': bullets_of('2511471')[0], 'action': 'pool', 'name': '仕佳光子', 'code': '688313',
     'q': 'sh688313', 'exch': ['sh', 'kc'], 'verdict': V_SJ_1471, 'conf': 'high',
     'beans': 280, 'column': '公告全知道', 'pub': '2026-10-21 22:08'},
    {'aid': '2511471', 'match': bullets_of('2511471')[1], 'action': 'abandon',
     'name': '（匿名线索·两家相似无唯一锚点）', 'code': '', 'column': '公告全知道', 'reason': V_AB2},
    {'aid': '2511471', 'match': BULLET_RJ, 'action': 'pool', 'name': '润建股份', 'code': '002929',
     'q': 'sz002929', 'exch': ['sz'], 'verdict': V_RJ, 'conf': 'high',
     'beans': 280, 'column': '公告全知道', 'pub': '2026-10-21 22:08'},
]
with open(DECISIONS, 'a', encoding='utf-8') as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')
print('webcheck_decisions.jsonl: +%d 条（3 pool + 2 abandon + 1 已入池标记）' % len(rows))

# ============================================================
# 自检
# ============================================================
d2 = json.loads(re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>',
                          open(HTML, encoding='utf-8').read(), re.S).group(1))
assert d2['version'] == '8.6' and len(d2['batches']) == 35 and len(d2['abandoned']) == 42
assert len(d2['watchlist']) == 39 and len(d2['stocks']) == 39 and len(d2['review']['stocks']) == 39
for b in d2['batches']:
    assert len(b['items']) == len(b['article']['teasers']), b['id']
teas_nos = sum(len(b['article']['teasers']) for b in d2['batches'])
item_nos = sum(len(b['items']) for b in d2['batches'])
pool_chk = sum(1 for x in d2['webcheck'] if x['status'] == 'pool')
inpool_names = {w['name'] for w in d2['watchlist']}
for nm in ('绿的谐波', '仕佳光子', '润建股份'):
    assert nm in inpool_names, nm
    hit = [w for w in d2['watchlist'] if w['name'] == nm][0]
    b_hit = [it for b in d2['batches'] if b['article'].get('aid') == hit['aid']
             for it in b['items'] if it.get('bulletNo') == hit['bulletNo']]
    assert b_hit and b_hit[0].get('scode') == hit['code'], nm
print('自检通过：%d 期 / 摘要 %d 条 = 裁决 %d 条 / abandoned %d / watchlist %d / baseP %s / webcheck pool %d'
      % (len(d2['batches']), teas_nos, item_nos, len(d2['abandoned']), len(d2['watchlist']),
         d2['quant']['baseP'], pool_chk))

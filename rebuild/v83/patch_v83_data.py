# -*- coding: utf-8 -*-
"""v8.3 数据层补录（承接用户“继续核验其余标的”指令）：

背景：v8.2 终检后做全量缺口分析，发现 17 期文章的 41 条公开摘要中 7 条尚未
逐条裁决（batches 只挂了入池标的，7 条放弃裁决仅存在于 webcheck 决策流水，
未与摘要逐条挂接）。本轮从财联社原文入手逐条独立复核：

  ① 2509149·摘要①「这家公司正式宣布成立“具身智能研究院”」
     → 机器人(300024) 入池（WEB-UNIQ：2025年报具身智能专章逐字对应，A股唯一）
  ② 2509816·摘要①「从云服务、大模型服务、数据服务到智能应用的全链路服务能力」
     → 太极股份(002368) 入池（WEB-UNIQ：2025年报核心竞争力专章逐字对应，全网唯一）
  ③ 2507498·摘要③ 航电/飞控/能源泛指 → 放弃（复数泛指，无锚点）
  ④ 2509149·摘要③ 西部数据(WDC) → 放弃（纳斯达克标的）
  ⑤ 2510217·摘要① MOM/MES/LES → 放弃（赛摩智能/赛意信息多家同类，无唯一锚点）
  ⑥ 2510217·摘要② Optimus厂商之一 → 放弃（“之一”泛化）
  ⑦ 2510298·摘要③ 超微电脑(SMCI) → 放弃（纳斯达克标的）

本脚本：补 2 只入池（行情/K线/富记录）+ 5 条放弃 items 挂接 batches +
webcheck 2 条 abandon→pool 改写 + abandoned 同步 + review 重建(35 只) +
baseP 重算 + 版本 8.3 + 注入 index.html。
"""
import json, os, re, sys

ROOT = '/workspace/cailianshe-dashboard'
HTML = os.path.join(ROOT, 'index.html')
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'rebuild', 'v82'))
import quant
import refresh

HORIZON = 10
V83_TIME = '2026-10-21 19:05'

# ---------- 读母版 ----------
h = open(HTML, encoding='utf-8').read()
m = re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>', h, re.S)
d = json.loads(m.group(1))
assert d['version'] == '8.2', d['version']
assert len(d['watchlist']) == 33 and len(d['stocks']) == 33

# ---------- 新标的行情（与 refresh.py 同一通道） ----------
raw = json.load(open('/tmp/v83_newstocks.json', encoding='utf-8'))

def close_of(q, day):
    for x in raw['kline'][q]:
        if x[0] == day:
            return x
    raise AssertionError('no bar ' + day)

def add_stock(q, name, exch):
    quote = raw['quotes'][q]
    kline = raw['kline'][q]
    minute = raw['minute'][q]
    assert kline and kline[-1][0] == '2026-10-21', kline[-1]
    assert len(minute) > 200, len(minute)
    d['stocks'][q] = {'name': name, 'price': quote['price'], 'prev': quote['prev'],
                      'change': round(quote['price'] - quote['prev'], 2), 'pct': quote['pct'],
                      'high': quote['high'], 'low': quote['low'], 'time': quote['time'],
                      'minute': minute, 'kline': kline}
    return quote, kline

q_robot, k_robot = add_stock('sz300024', '机器人', ['sz', 'cy'])
q_taiji, k_taiji = add_stock('sz002368', '太极股份', ['sz'])
assert len(k_robot) >= 71 and len(k_taiji) >= 71, (len(k_robot), len(k_taiji))

# 入池价口径与 v8.2 一致：入选日（文章发布日）最高价 = 盘中入池时点价
pi_robot = close_of('sz300024', '2026-10-20')[3]   # 13.01
pi_taiji = close_of('sz002368', '2026-10-20')[3]   # 13.88
gn_robot = round((q_robot['price'] / pi_robot - 1) * 100, 2)
gn_taiji = round((q_taiji['price'] / pi_taiji - 1) * 100, 2)
print('机器人  priceIn=%s now=%s gain=%s%%' % (pi_robot, q_robot['price'], gn_robot))
print('太极股份 priceIn=%s now=%s gain=%s%%' % (pi_taiji, q_taiji['price'], gn_taiji))

BULLET_ROBOT = '①工信部要求以人形机器人为“小切口”，带动具身智能大产业发展，分析师看好大模型持续进步有望加速通用具身落地，这家公司正式宣布成立“具身智能研究院”；'
BULLET_TAIJI = '①重磅！国家数据集团成立，分析师称2026年数据要素价值释放和产业开花有望加速，这家公司已形成从云服务、大模型服务、数据服务到智能应用的全链路服务能力；'

d['watchlist'].append({
    'name': '机器人', 'code': '300024', 'q': 'sz300024', 'exch': ['sz', 'cy'],
    'margin': False, 'sector': '',
    'reason': ('2025年年报「具身智能」专章逐字：“2025年，公司具身智能研究院正式成立，标志着公司全面布局具身智能技术、'
               '开启‘机器人+AI’融合创新的新里程”，与摘要“这家公司正式宣布成立‘具身智能研究院’”逐字对应。'
               '全网公开信源唯一性比对：A股仅机器人（300024）以自身名义成立“具身智能研究院”——新益昌（688383）与唐源电气（300789）'
               '1月6日挂牌者为两家共建的“具身智能联合研究院”（名称与主体数均不符）；天津大学/东北大学/中国科大为高校平台（非上市主体）；'
               '亚信科技（01675.HK）与ABB为联合实验室（港股且名称不符）。创业板（300024）吻合官方板块分布创业4。'),
    'fundamental': ('（全网比对确认·AI自主研判）A股“机器人第一股”（300024，中科院沈阳自动化所实控的国产工业机器人龙头）：'
                    '2025年4月新松具身智能研究院在沈阳揭牌，2025年报确认“正式成立”；WRC 2026（8-19）发布OneHub羿枢多机器人协同系统，'
                    '同台展出轮式/双足/四足/半身人形家族与仿生关节模组；2025年营收41.22亿元、各类机器人销量约13676台（同比+65%），'
                    '吉利义乌基地主焊线已部署近百台；半导体真空机械手等装备国产替代稳定量产。'
                    '工信部“以人形机器人为小切口带动具身智能大产业”政策下的人形机器人整机与具身智能底座标的。'),
    'outlook': '', 'dateIn': '2026-10-20', 'pub': '2026-10-20 08:12', 'beans': 380,
    'tier': 'webcheck', 'priceIn': pi_robot, 'priceNow': q_robot['price'], 'gainSince': gn_robot,
    'verifyTag': '全网比对确认', 'verify': True, 'tech': '', 'forecast': '—',
    'prob': None, 'probStatic': 55, 'conf': 'high', 'pct': q_robot['pct'], 'price': q_robot['price'],
    'column': '九点特供', 'batchId': 'wc20261020', 'verifyBasis': 'WEB-UNIQ',
    'aid': '2509149', 'bulletNo': 1, 'bullet': BULLET_ROBOT,
})

d['watchlist'].append({
    'name': '太极股份', 'code': '002368', 'q': 'sz002368', 'exch': ['sz'],
    'margin': False, 'sector': '',
    'reason': ('2025年年报核心竞争力专章逐字：“公司持续整合云计算、大数据、AI大模型及隐私计算等前沿技术，发挥‘离数近、用数广’的优势，'
               '布局太极云服务、数据智能服务等新型服务业态，打造从云服务、大模型服务、数据服务到智能应用的全链路服务能力”，'
               '与摘要“这家公司已形成从云服务、大模型服务、数据服务到智能应用的全链路服务能力”逐字对应；'
               '全网公开信源比对该四要素全链路表述唯一（开普云/浙大网新/云从科技等均为近似口径而非逐字）。深主板（002368）吻合官方板块分布主板6。'),
    'fundamental': ('（全网比对确认·AI自主研判）中国电科旗下政企数字化龙头（002368）：“云+数+智能”服务模式，'
                    '自主产品体系含普华操作系统、电科金仓数据库、金蝶天燕中间件、慧点科技办公软件；'
                    '10-20 国家数据集团在雄安揭牌（央企名录第28位、国务院国资委直接管理），数据要素市场化改革进入国家级主体规模化实施阶段，'
                    '公司卡位数据供给—流通—应用全链条；10-21 A股数据要素板块强势反弹、板块内10余只封板，公司涨停（+9.97%）。'),
    'outlook': '', 'dateIn': '2026-10-20', 'pub': '2026-10-20 20:43', 'beans': 280,
    'tier': 'webcheck', 'priceIn': pi_taiji, 'priceNow': q_taiji['price'], 'gainSince': gn_taiji,
    'verifyTag': '全网比对确认', 'verify': True, 'tech': '', 'forecast': '—',
    'prob': None, 'probStatic': 55, 'conf': 'high', 'pct': q_taiji['pct'], 'price': q_taiji['price'],
    'column': '财联社早知道', 'batchId': 'wc20261020', 'verifyBasis': 'WEB-UNIQ',
    'aid': '2509816', 'bulletNo': 1, 'bullet': BULLET_TAIJI,
})
assert len(d['watchlist']) == 35 and len(d['stocks']) == 35

# ---------- batches：7 条未裁决摘要全部挂接（2 入池 + 5 放弃） ----------
POOL_ROBOT = {
    'title': '机器人（300024）· 具身智能研究院', 'tags': ['利好', '上涨'], 'verified': True,
    'tier': 'webcheck',
    'content': ('摘要①→机器人。公开信源核验：2025年年报「具身智能」专章逐字“2025年，公司具身智能研究院正式成立，'
                '标志着公司全面布局具身智能技术、开启‘机器人+AI’融合创新的新里程”，与摘要逐字对应；'
                '全网唯一性比对：A股仅机器人（300024）以自身名义成立“具身智能研究院”'
                '（新益昌/唐源电气为两家共建“联合研究院”，名称与主体数均不符；天大/东大/中科大为高校平台）。'
                '创业板（300024）吻合官方板块分布创业4。'),
    'stock': '机器人', 'scode': '300024', 'aid': '2509149', 'bulletNo': 1,
}
POOL_TAIJI = {
    'title': '太极股份（002368）· 云数智全链路服务能力', 'tags': ['利好', '上涨'], 'verified': True,
    'tier': 'webcheck',
    'content': ('摘要①→太极股份。公开信源核验：2025年年报核心竞争力专章逐字“打造从云服务、大模型服务、数据服务到智能应用的全链路服务能力”，'
                '与摘要逐字对应；全网比对该四要素全链路表述唯一。深主板（002368）吻合官方板块分布主板6。'
                '10-21 数据要素板块强势反弹、板块内10余只封板，公司涨停。'),
    'stock': '太极股份', 'scode': '002368', 'aid': '2509816', 'bulletNo': 1,
}
ABANDON = {
    '2507498-3': {
        'title': '摘要③→航电/飞控/能源系统零部件供应商（泛指多家）', 'tags': [], 'verified': False,
        'tier': 'gold',
        'content': ('摘要③“航电、飞控和能源系统在飞行汽车领域同样占据高成本占比，这些企业已逐步进入该领域成为零部件供应商”'
                    '为复数泛指，未点名单一主体，全网无逐字对应公告，无法唯一锁定标的，按铁律宁缺毋滥放弃，留痕备查。'),
        'stock': '', 'scode': '', 'aid': '2507498', 'bulletNo': 3,
    },
    '2509149-3': {
        'title': '摘要③→西部数据（WDC·NASDAQ）· 非A股标的', 'tags': [], 'verified': False,
        'tier': 'webcheck',
        'content': ('摘要③指向西部数据（Western Digital, WDC.NASDAQ）盘后涨6.09%（高容量ePMR与UltraSMR HDD需求提振），'
                    '为美股标的，无A股唯一映射锚点，按铁律宁缺毋滥放弃，留痕备查。'),
        'stock': '', 'scode': '', 'aid': '2509149', 'bulletNo': 3,
    },
    '2510217-1': {
        'title': '摘要①→MOM/MES/LES 智能工厂软件（多家同类）', 'tags': [], 'verified': False,
        'tier': 'webcheck',
        'content': ('摘要①“公司MOM、MES、LES等产品是智能工厂的生产指挥与数据管控底座”无法逐字锁定单一主体：'
                    '赛摩智能（300466）年报列“企业运营管理系统MOM、制造执行系统MES、物流自动化管控系统LES等系列产品”，'
                    '赛意信息（300687）iMOM体系含MOM-LES/iMOM-MES模块，同类产品组合多家具备，无全市场唯一锚点，'
                    '按铁律宁缺毋滥放弃，留痕备查。'),
        'stock': '', 'scode': '', 'aid': '2510217', 'bulletNo': 1,
    },
    '2510217-2': {
        'title': '摘要②→Optimus 关键零部件厂商（“之一”泛化）', 'tags': [], 'verified': False,
        'tier': 'webcheck',
        'content': ('摘要②“公司是Optimus关键零部件厂商之一”表述泛化，数十家A股公司均自称特斯拉Optimus供应链成员，'
                    '无逐字唯一锚点，按铁律宁缺毋滥放弃，留痕备查。'),
        'stock': '', 'scode': '', 'aid': '2510217', 'bulletNo': 2,
    },
    '2510298-3': {
        'title': '摘要③→超微电脑（SMCI·NASDAQ）· 非A股标的', 'tags': [], 'verified': False,
        'tier': 'webcheck',
        'content': ('摘要③指向超微电脑（Super Micro, SMCI.NASDAQ）盘后涨14%、Q1初步业绩营收超预期，'
                    '为美股标的，无A股唯一映射锚点，按铁律宁缺毋滥放弃，留痕备查。'),
        'stock': '', 'scode': '', 'aid': '2510298', 'bulletNo': 3,
    },
}
NOTES = {
    'b2507498': ('本篇官方板块分布 创业板3+科创板1+主板2；公开摘要共 3 条，按「摘要条数 = 股票数硬上限」铁律，本篇最多入池 3 只，'
                 '实际入池 2 只（万丰奥威=摘要①、英搏尔=②；摘要③“航电、飞控和能源系统……这些企业”为复数泛指，'
                 '未点名单一主体、全网无逐字对应公告，无法唯一锁定，宁缺毋滥放弃并留痕）。'),
    'b2509149': ('本篇官方板块分布 主板5+科创板1+创业板4；公开摘要共 3 条，按「摘要条数 = 股票数硬上限」铁律，本篇最多入池 3 只，'
                 '实际入池 2 只（机器人=摘要①、中京电子=②；摘要③西部数据（WDC）为纳斯达克标的，无A股唯一锚点，放弃留痕）。'),
    'b2509816': ('本篇官方板块分布 科创板2+主板6；公开摘要共 3 条，按「摘要条数 = 股票数硬上限」铁律，本篇最多入池 3 只，'
                 '实际入池 3 只（太极股份=摘要①、国新健康=②、星网锐捷=③），达本篇上限。'),
    'b2510217': ('本篇官方板块分布 创业板2+主板1；公开摘要共 3 条，按「摘要条数 = 股票数硬上限」铁律，本篇最多入池 3 只，'
                 '实际入池 1 只（海正药业=③；摘要①MOM/MES/LES同类产品组合多家具备、摘要②“Optimus关键零部件厂商之一”泛化，'
                 '均无全市场唯一锚点，宁缺毋滥放弃并留痕）。'),
    'b2510298': ('本篇官方板块分布 主板7+创业板1+科创板2；公开摘要共 3 条，按「摘要条数 = 股票数硬上限」铁律，本篇最多入池 3 只，'
                 '实际入池 2 只（索辰科技=①、启明星辰=②；摘要③超微电脑（SMCI）为纳斯达克标的，无A股唯一锚点，放弃留痕）。'),
}
COMPANIES = {'b2509149': 2, 'b2509816': 3}   # 入池只数变化的两期

for b in d['batches']:
    bid = b['id']
    aid = b['article']['aid']
    if bid == 'b2509149':
        b['items'].append(POOL_ROBOT)
        b['items'].append(ABANDON['2509149-3'])
    elif bid == 'b2509816':
        b['items'].append(POOL_TAIJI)
    elif bid == 'b2507498':
        b['items'].append(ABANDON['2507498-3'])
    elif bid == 'b2510217':
        b['items'].append(ABANDON['2510217-1'])
        b['items'].append(ABANDON['2510217-2'])
    elif bid == 'b2510298':
        b['items'].append(ABANDON['2510298-3'])
    else:
        continue
    b['items'].sort(key=lambda x: x.get('bulletNo') or 0)
    b['note'] = NOTES[bid]
    if bid in COMPANIES:
        b['companies'] = COMPANIES[bid]
    # 断言：每期 items 与摘要条数一一对应
    assert len(b['items']) == len(b['article']['teasers']), (bid, len(b['items']))

total_items = sum(len(b['items']) for b in d['batches'])
total_teasers = sum(len(b['article']['teasers']) for b in d['batches'])
print('batches items=%d / teasers=%d（17 期）' % (total_items, total_teasers))
assert total_items == total_teasers == 41

# ---------- webcheck：2 条 abandon → pool 改写；1 条理由修正 ----------
VERDICT_ROBOT = ('2025年年报「具身智能」专章逐字“2025年，公司具身智能研究院正式成立，标志着公司全面布局具身智能技术、'
                 '开启‘机器人+AI’融合创新的新里程”；全网唯一性比对：A股仅机器人（300024）以自身名义成立“具身智能研究院”'
                 '（新益昌/唐源电气1月6日挂牌者为两家共建“具身智能联合研究院”，名称与主体数均不符；天大/东大/中科大为高校平台；'
                 '亚信科技01675.HK与ABB为联合实验室）；创业板300024吻合官方板块分布创业4。')
VERDICT_TAIJI = ('2025年年报核心竞争力专章逐字“打造从云服务、大模型服务、数据服务到智能应用的全链路服务能力”；'
                 '全网唯一性比对：该四要素全链路表述仅太极股份（002368）年报逐字载明（开普云/浙大网新/云从科技等为近似口径）；'
                 '深主板002368吻合官方板块分布主板6；10-21数据要素板块10余只封板，公司涨停。')
VERDICT_MOM = ('MOM/MES/LES同类产品组合多家具备：赛摩智能（300466）年报列“企业运营管理系统MOM、制造执行系统MES、'
               '物流自动化管控系统LES等系列产品”，赛意信息（300687）iMOM体系含MOM-LES/iMOM-MES模块；'
               '无逐字唯一锚点锁定单一主体，宁缺毋滥')

n_pool = n_ref = 0
for x in d['webcheck']:
    if x.get('aid') == '2509149' and '具身智能研究院' in (x.get('bullet') or '') and x['status'] == 'abandon':
        x['status'] = 'pool'
        x['resolvedTo'] = '机器人'
        x['verdict'] = VERDICT_ROBOT
        n_pool += 1
    elif x.get('aid') == '2509816' and '全链路服务能力' in (x.get('bullet') or '') and x['status'] == 'abandon':
        x['status'] = 'pool'
        x['resolvedTo'] = '太极股份'
        x['verdict'] = VERDICT_TAIJI
        n_pool += 1
    elif x.get('aid') == '2510217' and 'MOM、MES、LES' in (x.get('bullet') or '') and x['status'] == 'abandon':
        x['verdict'] = VERDICT_MOM
        n_ref += 1
assert n_pool == 2 and n_ref == 1, (n_pool, n_ref)
print('webcheck: abandon→pool %d 条；理由修正 %d 条' % (n_pool, n_ref))

# ---------- abandoned：移除 2 条已入池、修正 1 条理由 ----------
before = len(d['abandoned'])
d['abandoned'] = [a for a in d['abandoned']
                  if not (a.get('aid') == '2509149' and '具身智能研究院' in (a.get('match') or ''))
                  and not (a.get('aid') == '2509816' and '全链路服务能力' in (a.get('match') or ''))]
for a in d['abandoned']:
    if a.get('aid') == '2510217' and 'MOM' in (a.get('match') or ''):
        a['reason'] = ('MOM/MES/LES同类产品组合多家具备：赛摩智能(300466)年报列MOM/MES/LES等系列产品，'
                       '赛意信息(300687)iMOM体系含MOM-LES/iMOM-MES模块；无逐字唯一锚点锁定单一主体，宁缺毋滥')
print('abandoned: %d → %d 条' % (before, len(d['abandoned'])))
assert len(d['abandoned']) == before - 2 == 36

# ---------- review 重建（35 只；逻辑同 rebuild_v82_review.py） ----------
idx_bars = quant.norm_bars(d['quant']['index']['bars'])
STATE = quant.index_state(idx_bars, HORIZON)
klmap = {}
for w in d['watchlist']:
    st = d['stocks'].get(w['q']) or {}
    if st.get('kline'):
        klmap[w['q']] = {'bars': st['kline'], 'name': w['name']}
print('日K可用: %d / %d' % (len(klmap), len(d['watchlist'])))
exp, _ = quant.build_experience(klmap, None, HORIZON)
print('baseP(exp)=%.4f（存档原值 %s）' % (exp.get('baseP', 0), d['quant'].get('baseP')))
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
assert len(review_stocks) == 35

# baseP 存档值同步为 35 只池实测值（浏览器 QX_BASE 与 Python 复盘同源，保两端对拍一致）
old_base = d['quant'].get('baseP')
d['quant']['baseP'] = round(exp.get('baseP', old_base), 4)
print('quant.baseP: %s → %s' % (old_base, d['quant']['baseP']))

# ---------- 版本 / 时间戳 / 历史 ----------
d['version'] = '8.3'
d['lastUpdated'] = ('2026-10-21（v8.3：继续核验其余标的——17 期 41 条公开摘要逐条裁决闭环；'
                    '2509149①「具身智能研究院」按 2025 年报唯一锚点补录机器人(300024)、'
                    '2509816①「全链路服务能力」按 2025 年报核心竞争力专章唯一锚点补录太极股份(002368)，在池 33→35 只；'
                    '其余 5 条摘要（泛指/美股映射/Optimus 泛化/MOM-MES-LES 多家同类）维持放弃并挂接期次备查留痕；'
                    '行情分时同步至 2026-10-21 收盘）')
d['collectTime'] = '2026-10-21 19:05（v8.3 补录采集·自动通道）'
d['quoteTime'] = '2026-10-21 收盘'
d['history'].append({
    'version': '8.3', 'time': V83_TIME,
    'note': ('继续核验其余标的（用户指令）：对 17 期文章 41 条公开摘要做全量缺口分析，发现 7 条摘要尚未与期次备查挂接裁决，'
             '从财联社原文逐条独立复核——①2509149·摘要①“这家公司正式宣布成立‘具身智能研究院’”：历史放弃理由“全网无对应上市公司信源”不成立，'
             '机器人（300024）2025年年报「具身智能」专章逐字“公司具身智能研究院正式成立”，且全网唯一性比对确认A股仅其以自身名义成立'
             '（新益昌/唐源电气为两家共建联合研究院、高校平台与港股联合实验室均不符），按 WEB-UNIQ 入池；'
             '②2509816·摘要①“从云服务、大模型服务、数据服务到智能应用的全链路服务能力”：历史放弃理由“表述泛化”不成立，'
             '太极股份（002368）2025年年报核心竞争力专章逐字载明该四要素全链路表述且全网唯一，按 WEB-UNIQ 入池；'
             '③2507498·摘要③（航电/飞控/能源泛指多家）、④2509149·摘要③（西部数据WDC·纳斯达克）、'
             '⑤2510217·摘要①（MOM/MES/LES，赛摩智能300466与赛意信息300687多家同类）、'
             '⑥2510217·摘要②（Optimus关键零部件厂商“之一”泛化）、⑦2510298·摘要③（超微电脑SMCI·纳斯达克）'
             '共 5 条维持放弃，理由逐条补强并全部挂接期次备查（2 入池 + 5 放弃 = 7 条，41 条摘要全部有裁决）；'
             'webcheck 2 条 abandon→pool 改写、abandoned 38→36 条；review 重建 35 只；quant.baseP 按 35 只池重算同步。'),
})

# ---------- 注入 index.html ----------
blob = json.dumps(d, ensure_ascii=False, separators=(',', ':'))
assert '</script>' not in blob
h2 = re.sub(r'(<script id="MONITOR_DATA" type="application/json">).*?(</script>)',
            lambda mm: mm.group(1) + blob + mm.group(2), h, count=1, flags=re.S)
assert h2 != h and 'MONITOR_DATA' in h2
open(HTML, 'w', encoding='utf-8').write(h2)
print('注入完成：index.html %d bytes' % len(h2.encode('utf-8')))

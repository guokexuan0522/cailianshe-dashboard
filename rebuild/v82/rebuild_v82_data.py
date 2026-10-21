# -*- coding: utf-8 -*-
"""v8.2 数据层重建（承接 9 项用户反馈中的 #41 #42 #6 #7 #4）：
1. 2510883（盘中宝 10-21 14:43）标的替换：删除中恒电气/科华数据，新增杰瑞股份
2. 全部入池标的补 aid + 摘要条目编号（期次备查可追溯，铁律验收口径）
3. webcheck 2510883 pool 决策改写 + 两条放弃留痕；2510253 富临精工 pool 条目重建
4. 重建 batches 期次备查（17 期）
5. 重建 review 今日收盘数据复盘（含量化建议）
"""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refresh

HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')

# ---------- 读母版 ----------
h = open(HTML, encoding='utf-8').read()
m = re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>', h, re.S)
d = json.loads(m.group(1))
assert d['version'] == '8.1', d['version']

# ---------- 一、2510883 标的替换 ----------
REMOVE = ['002364', '002335']          # 中恒电气、科华数据（HVDC 误判）
d['watchlist'] = [w for w in d['watchlist'] if w['code'] not in REMOVE]
for q in ('sz002364', 'sz002335'):
    d['stocks'].pop(q, None)
assert len(d['watchlist']) == 32, len(d['watchlist'])

# 杰瑞股份：真实行情 / 分时 / 日K（与 refresh.py 同一通道抓取）
q = 'sz002353'
quote = refresh.fetch_quotes([q])[q]
kline = refresh.fetch_kline(q)
minute = refresh.fetch_minute(q)
assert kline and kline[-1][0] == '2026-10-21', kline[-1]
assert len(minute) > 200, len(minute)
price_in = 90.31          # 盘中宝 14:43 发布时刻分时价（发布时点入池价）
price_now = quote['price']
gain = round((price_now / price_in - 1) * 100, 2)

d['watchlist'].append({
    "name": "杰瑞股份", "code": "002353", "q": q, "exch": ["sz"],
    "margin": False, "sector": "", "aid": "2510883", "bulletNo": 0,
    "bullet": "有望成为短期内最优的数据中心供电解决方案，2026年为国内厂商出海元年，龙头订单累计获得逾200亿元订单，这家公司已供货国际巨头。",
    "reason": "盘中宝原文逐字锚点三重唯一锁定：①「短期内最优」对应燃气轮机12-18个月即可交付投产、自建燃气电站成科技巨头最优解（中国经济网/经济日报原文逐字）；②「龙头订单累计获得逾200亿元」对应2026半年报披露自2025年11月起数据中心燃气轮机发电机组及配套设备订单累计超31亿美元（约209亿元），全市场唯一；③「已供货国际巨头」对应7-22公告与某国际知名云服务提供商签14.65亿美元供应合同、并与西门子能源/FTAI Power签战略合作。同日财联社电报：燃气轮机概念拉升，杰瑞股份涨停",
    "fundamental": "（全网比对确认·AI自主研判）油服装备起家、以成套电力解决方案切入AIDC供电：自2025年11月起累计斩获数据中心燃气轮机发电机组订单超31亿美元（约209亿元，2026半年报）；2026-07-22公告与某国际知名云服务提供商签14.65亿美元供应合同；与西门子能源签SGT燃气轮机战略合作、与FTAI Power设合资公司锁定机头资源；AIDC微电网一体化方案完成全工况验证并取得「燃气发电+混合储能+固态变压器」一体化供电项目订单；2026H1营收76.5亿(+10.8%)、归母净利12.0亿(-3.6%)，高端装备板块收入41.89亿占54.79%，订单集中在2027年及以后交付",
    "outlook": "", "dateIn": "2026-10-21", "pub": "2026-10-21 14:43", "beans": 280,
    "tier": "webcheck", "priceIn": price_in, "priceNow": price_now, "gainSince": gain,
    "verifyTag": "全网比对确认", "verify": True, "tech": "", "forecast": "—",
    "prob": None, "probStatic": 55, "conf": "mid", "pct": quote['pct'], "price": price_now,
    "column": "盘中宝", "batchId": "wc20261021", "verifyBasis": "WEB-UNIQ",
})
d['stocks'][q] = {"name": "杰瑞股份", "price": price_now, "prev": quote['prev'],
                  "change": round(price_now - quote['prev'], 2), "pct": quote['pct'],
                  "high": quote['high'], "low": quote['low'], "time": quote['time'],
                  "minute": minute, "kline": kline}
assert len(d['watchlist']) == 33, len(d['watchlist'])
assert len(d['stocks']) == 33, len(d['stocks'])

# ---------- 二、webcheck 修正 ----------
wc = d['webcheck']
# 2.1 2510883 pool：中恒电气 → 杰瑞股份
for x in wc:
    if x['aid'] == '2510883' and x['status'] == 'pool':
        x['resolvedTo'] = '杰瑞股份'
        x['verdict'] = ("原文锚点三重唯一锁定：①「短期内最优」=燃气轮机12-18个月交付投产、自建燃气电站成科技巨头最优解（中国经济网《中国燃气轮机产业链卡位崛起》逐字）；"
                        "②「龙头订单累计获得逾200亿元」=杰瑞股份2026半年报「自2025年11月至今数据中心燃气轮机发电机组及配套设备订单累计超31亿美元（约209亿元）」，全市场唯一；"
                        "③「已供货国际巨头」=7-22公告与某国际知名云服务提供商签14.65亿美元供应合同，另与西门子能源签SGT战略合作、与FTAI Power设合资。"
                        "同日财联社电报2510595：燃气轮机概念拉升，杰瑞股份涨停。板块分布主板2，本只为主板，另一只无唯一锚点按宁缺毋滥放弃。")
# 2.2 2510253：拆掉错乱条目（abandon+resolvedTo=富临精工+name=宁德时代+bullet=标签串）
wc = [x for x in wc if not (x['aid'] == '2510253' and x.get('name') == '宁德时代')]
wc.append({"aid": "2510253", "column": "公告全知道",
           "title": "【公告全知道】碳化硅+先进封装+第三代半导体+金刚石+AI眼镜！公司Q3净利润环比增长超44倍",
           "pub": "2026-10-20 22:06", "dateIn": "2026-10-21", "beans": 280,
           "bullet": "③人形机器人+锂电池+储能+宁德时代+华为！公司拟5亿元投建机器人智能电关节项目。",
           "status": "pool", "resolvedTo": "富临精工",
           "verdict": "公告摘要本体即公告：2026-10-20晚公告与绵阳涪城区政府签署《机器人智能电关节项目投资协议》，计划总投资5亿元，实施主体子公司四川班巧智能（上证报/中证网/证券时报多方一致）；「5亿元+机器人智能电关节项目」为唯一硬锚点，深主板创业板（300432）与官方板块分布创业1吻合"})
wc.append({"aid": "2510253", "column": "公告全知道",
           "title": "【公告全知道】碳化硅+先进封装+第三代半导体+金刚石+AI眼镜！公司Q3净利润环比增长超44倍",
           "pub": "2026-10-20 22:06", "dateIn": "2026-10-21", "beans": 280,
           "bullet": "人形机器人+锂电池+储能+宁德时代+华为",
           "status": "abandon", "resolvedTo": "", "name": "宁德时代", "code": "300750",
           "verdict": "标签串假阳性（铁律②）：该串为概念标签堆叠而非公司特异性描述，加号分隔多段无主体指向，剔除；宁德时代不在本篇官方板块分布内，且无任何逐字公告锚点"})
# 2.3 2510883 两条放弃留痕（中恒电气/科华数据）
wc.append({"aid": "2510883", "column": "盘中宝",
           "title": "【盘中宝】有望成为短期内最优的数据中心供电解决方案，2026年为国内厂商出海元年，龙头订单累计获得逾200亿元订单",
           "pub": "2026-10-21 14:43", "dateIn": "2026-10-21", "beans": 280,
           "bullet": "有望成为短期内最优的数据中心供电解决方案，2026年为国内厂商出海元年，龙头订单累计获得逾200亿元订单，这家公司已供货国际巨头。",
           "status": "abandon", "resolvedTo": "", "name": "中恒电气", "code": "002364",
           "verdict": "v8.1 误判、v8.2 更正：原以「HVDC龙头+出海元年+200亿订单」对应本条，属典型的先有标的再凑文章特征。逐项复核：①中恒电气HVDC累计订单口径约100-150亿元，与「逾200亿元」不符；②HVDC 2026年仍处试点验证期，与「短期内最优」（燃气轮机12-18个月即可交付投产）不符；③该标的无任何与「逾200亿元」匹配的公开订单披露。按铁律从投研池删除，留痕备查"})
wc.append({"aid": "2510883", "column": "盘中宝",
           "title": "【盘中宝】有望成为短期内最优的数据中心供电解决方案，2026年为国内厂商出海元年，龙头订单累计获得逾200亿元订单",
           "pub": "2026-10-21 14:43", "dateIn": "2026-10-21", "beans": 280,
           "bullet": "2026年为国内厂商出海元年",
           "status": "abandon", "resolvedTo": "", "name": "科华数据", "code": "002335",
           "verdict": "v8.1 误判、v8.2 更正：原落地锚点为行业性表述「2026年为国内厂商出海元年」——该表述无任何公司特异性指向，直接违反铁律（NONE：仅有行业指代）。同一 bullet 已由杰瑞股份以唯一硬锚点（209亿元累计订单）锁定，不得二次落地。按铁律从投研池删除，留痕备查"})
d['webcheck'] = wc

# ---------- 三、abandoned 留痕补齐 ----------
ab = d['abandoned']
for a in ({"aid": "2510883", "name": "中恒电气", "code": "002364", "match": "龙头订单累计获得逾200亿元订单，这家公司已供货国际巨头",
           "column": "盘中宝", "dateIn": "2026-10-21",
           "reason": "v8.1误判·v8.2更正：HVDC累计订单口径（约100-150亿）与「逾200亿元」不符，「短期内最优」对应燃气轮机而非HVDC，属先有标的再凑特征；该条 bullet 唯一硬锚点已由杰瑞股份（209亿元订单）锁定"},
          {"aid": "2510883", "name": "科华数据", "code": "002335", "match": "2026年为国内厂商出海元年",
           "column": "盘中宝", "dateIn": "2026-10-21",
           "reason": "v8.1误判·v8.2更正：落地锚点为行业性表述、无公司特异性指向，违反铁律；同一 bullet 已由杰瑞股份唯一锁定，不得二次落地"},
          {"aid": "2510253", "name": "宁德时代", "code": "300750", "match": "人形机器人+锂电池+储能+宁德时代+华为",
           "column": "公告全知道", "dateIn": "2026-10-21",
           "reason": "概念标签串假阳性（铁律②）：加号堆叠标签非公司特异性描述，无逐字公告锚点，且不在本篇官方板块分布内"}):
    if not any(x['aid'] == a['aid'] and x.get('name') == a['name'] for x in ab):
        ab.append(a)
d['abandoned'] = ab

json.dump({'ok': True}, open(os.devnull, 'w'))
open('/tmp/stage1.json', 'w', encoding='utf-8').write(json.dumps(d, ensure_ascii=False))
print('stage1 ok: watchlist', len(d['watchlist']), 'stocks', len(d['stocks']),
      'webcheck', len(d['webcheck']), 'abandoned', len(d['abandoned']))

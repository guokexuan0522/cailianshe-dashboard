# -*- coding: utf-8 -*-
"""v8.2 数据层 patch：ruleCats 融合用户亲定铁律 / 超期彻底清除 / 栏目文案修正 / 版本升级 / 注入 index.html"""
import json, re, sys, datetime

SRC = '/tmp/stage3.json'
TODAY = '2026-10-21'

# ---------- 交易日历（与页面 CAL_HOLIDAYS 同源，证监会 2026 年安排）----------
CAL_HOLIDAYS = {
    '2026-01-01', '2026-01-02',
    '2026-02-16', '2026-02-17', '2026-02-18', '2026-02-19', '2026-02-20', '2026-02-23',
    '2026-04-06',
    '2026-05-01', '2026-05-04', '2026-05-05',
    '2026-06-19',
    '2026-09-25',
    '2026-10-01', '2026-10-02', '2026-10-05', '2026-10-06', '2026-10-07',
}


def is_trading_day(ds):
    d = datetime.date.fromisoformat(ds)
    if d.weekday() >= 5:
        return False
    return ds not in CAL_HOLIDAYS


def td_index(date_in, today=TODAY):
    """dateIn 至今（含今日）的交易日起点序号：入池当日=1"""
    if not date_in:
        return 0
    d0 = datetime.date.fromisoformat(date_in)
    d1 = datetime.date.fromisoformat(today)
    n, d = 0, d0
    while d <= d1:
        if is_trading_day(d.isoformat()):
            n += 1
        d += datetime.timedelta(days=1)
    return n


d = json.load(open(SRC, encoding='utf-8'))

# ============================================================
# 一、超过 10 个交易日的候选/待比对股票：从看板彻底删除（含期次备查与说明信息全部抹除）
# ============================================================
removed = []
keep = []
for c in d.get('candidates') or []:
    if td_index(c.get('dateIn')) >= 10:
        removed.append(('比对候选池', c.get('name'), c.get('code')))
    else:
        keep.append(c)
d['candidates'] = keep

keep = []
for x in d.get('webcheck') or []:
    if x.get('status') == 'pending' and td_index(x.get('dateIn')) >= 10:
        removed.append(('全网比对·待比对', x.get('name') or x.get('match'), x.get('code')))
    else:
        keep.append(x)
d['webcheck'] = keep

# 期次备查与说明信息：抹除被彻底删除股票的标识，不留残迹
purge_codes = {r[2] for r in removed if r[2]}
purge_names = {r[1] for r in removed if r[1]}
for b in d.get('batches') or []:
    b['items'] = [it for it in b.get('items') or [] if not (it.get('purged') or it.get('scode') in purge_codes)]
    b['companies'] = len(b['items'])
print('[purge] 超期彻底删除:', len(removed), '条；涉及代码:', purge_codes or '无')

# ============================================================
# 二、ruleCats 融合：取消「〇、用户亲定铁律」单独置顶，按分类并入 11 条，冲突条款以亲定内容修正
# ============================================================
cats = d['ruleCats']
own = cats[0]
own_items = own['items']
rest = cats[1:]
by_name = {c['name']: c for c in rest}

# —— 冲突修正（第 4 点联动）：栏目清单补全 盘中宝 / 九点特供 / 研选•行业数据 ——
FULL_COLS = '公告全知道、财联社早知道、狙击龙虎榜、盘中宝、九点特供、风口研报·洞察、金牌纪要库、研选•行业数据'
c1 = by_name['一、监控范围与栏目']
for it in c1['items']:
    if '当前在池真实分类' in it:
        it_new = re.sub(r'当前在池真实分类：[^。]*。', '当前在池真实分类：' + FULL_COLS + '。', it)
        c1['items'][c1['items'].index(it)] = it_new
c10 = by_name['十、展示口径']
for it in c10['items']:
    if it.startswith('栏目分类：按财联社原栏目名区分'):
        c10['items'][c10['items'].index(it)] = ('栏目分类：按财联社原栏目名区分（公告全知道📢 / 财联社早知道☀ / 狙击龙虎榜🎯 / '
                    '盘中宝⚡ / 九点特供🕘 / 风口研报·洞察🔭 / 金牌纪要库🏅 / 研选•行业数据📊），'
                    '以色块、图标、卡片顶边、表格行底色、图表柱色统一标识。')

# —— 用户亲定 9 条按分类并入（标注【用户亲定】以示权威来源）——
def ins(cat_name, text, pos=None):
    c = by_name[cat_name]
    if pos is None:
        c['items'].append(text)
    else:
        c['items'].insert(pos, text)

# ① 价格是第一道硬关 → 二、抓取门槛（置顶）
ins('二、抓取门槛',
    '【用户亲定·第一道硬关】只抓取 ≥280 微信豆的高价值文章；180 微信豆的一般信息类/普通研报类文章直接不要（对超短线/强势票策略无价值）。', 0)
# ② 摘要条数 = 股票数量硬上限 → 四、入池流程与核验
ins('四、入池流程与核验',
    '【用户亲定】摘要条数 = 股票数量硬上限：摘要有 ①②③ 几条，这篇文章就只对应几只股票。三条摘要绝不能搞出四五个——多出来的必是错误信息，会误导入池与投资决策。绝不外延。')
# ③ 全网比对确认（第三道关）→ 三、信息源铁律
ins('三、信息源铁律',
    '【用户亲定·第三道关】全网比对确认：摘要未点名具体上市公司的，拿摘要中的公告内容特征与全网公开信息（公告原文/研报/权威媒体）比对定位。比对上→入池；匹配度相当高但非一一精确→进候选池；匹配不上或匹配度不高→暂时放弃，宁缺毋滥，绝不马马虎虎。')
# ④ 笼统行业文整篇放弃 → 三、信息源铁律
ins('三、信息源铁律',
    '【用户亲定】笼统行业文/趋势文，公开信息无法对具体股票准确定位、没有一一对应股票特征的，整篇彻底放弃（宁缺毋滥）。')
# ⑤ 点名但价值在趋势/价值分析的入池条件 → 四、入池流程与核验
ins('四、入池流程与核验',
    '【用户亲定】点明了股票名称但文章价值在趋势/价值分析的：需同时满足 前瞻性看好 + 公开信息有对应 + 上涨概率研判高 才入池；否则不入池（无近期最直接利好，入池意义不大）。')
# ⑥ 负面消息绝对排除 → 三、信息源铁律
ins('三、信息源铁律',
    '【用户亲定】负面消息绝对排除：行业走向衰落、盈利能力下降、业绩下滑、减持、处罚、退市风险等——即使文章收费再高、点了名，也绝不收录。绝不逆向选择衰落行业/有负面消息的股票。')
# ⑦ 系统根本目的 → 九、流水线与运维（置顶）
ins('九、流水线与运维',
    '【用户亲定】系统根本目的：全自动抓取→按铁律筛选→对入池股票持续数据追踪（涨跌/成功率），用一段时间的实盘表现检验这套筛选的可信度，作为投资参考。全程最大限度减少人工干预，用户只在云端网页查看结果与数据动态。', 0)
# v8.0 数据起始日 → 七、数据与文件铁律
ins('七、数据与文件铁律',
    '【用户亲定·v8.0】数据源起始日为 2026-10-18：此前 10-11~10-17 窗口的数据与文章全部清空不作数，看板从 10-18 发布的文章起按现行铁律重新抓取、比对、入池；投研池/候选池/文章期次/复盘统计全部从零开始累计。')

d['ruleCats'] = rest
print('[ruleCats] 融合后分类数:', len(rest), '（用户亲定铁律已按分类并入，取消单独置顶）')
for c in rest:
    n_own = sum(1 for it in c['items'] if it.startswith('【用户亲定'))
    print('   ', c['name'], '→', len(c['items']), '条（含亲定', n_own, '条）')

# ============================================================
# 三、版本升级 8.1 → 8.2 + 修订记录
# ============================================================
d['version'] = '8.2'
d.setdefault('history', []).append({
    'version': '8.2', 'time': '2026-10-21 18:30',
    'note': ('按用户 9 项反馈彻查修正：①自选股跨浏览器同步重写——同步链接改为携带完整自选信息（代码/自选价/人工录入标记/名称/市场），'
             '任何设备任何方式打开即完整恢复，恢复语义改为合并而非覆盖；②今日收盘数据复盘修复——重建 review 数据（33 只技术面要点+操盘建议），'
             '日期与只数动态计算，自选股正常显示；③「复制同步链接」补充用法与作用说明；④修正栏目分类错配——COLUMNS 补齐盘中宝/九点特供/研选•行业数据，'
             '2510883 期次误判标的中恒电气/科华数据已剔除、按原文唯一锚点替换为杰瑞股份（累计订单逾 200 亿元，全网唯一对应）；'
             '⑤全网比对与放弃审计重构——只保留「待比对」「已放弃」两栏，已入池股票不再冗余出现，两区均支持全部收起，超过 10 个交易日的候选/待比对股票'
             '连同期次备查与说明信息自动彻底抹除；⑥核验列逻辑修正——按 verify/verifyTag 真实状态展示，不再全部误显「推断·待正文确认」；'
             '⑦期次备查重建——17 期 34 条全部含文章摘要原文/板块分布/原文链接/逐只入选依据；⑧用户亲定铁律融合——取消单独置顶，9 条按分类并入 11 类铁律，'
             '冲突条款以亲定内容修正（栏目清单同步补全）；⑨自选股与投研池新增分类筛选——按财联社栏目来源过滤，自选股额外支持「人工录入」分类。'
             '全部入池标的已按修正后铁律从财联社原文逐字复核（摘要条数=股票数硬上限 17/17 期通过）。')
})
print('[version] 8.1 → 8.2，history 条数:', len(d['history']))

# ============================================================
# 四、注入 index.html 的 MONITOR_DATA
# ============================================================
html = open('/workspace/cailianshe-dashboard/index.html', encoding='utf-8').read()
m = re.search(r'(<script id="MONITOR_DATA" type="application/json">)(.*?)(</script>)', html, re.S)
if not m:
    print('!! 未找到 MONITOR_DATA'); sys.exit(1)
new_json = json.dumps(d, ensure_ascii=False, separators=(',', ':'))
assert '</script>' not in new_json.lower(), 'JSON 内含 </script>，需转义'
html = html[:m.start(2)] + new_json + html[m.end(2):]
open('/workspace/cailianshe-dashboard/index.html', 'w', encoding='utf-8').write(html)
print('[inject] MONITOR_DATA 已更新，新长度:', len(new_json))

# ============================================================
# 五、同步 landed.log 与 webcheck_decisions.jsonl（2510883 杰瑞股份）
# ============================================================
import os
lp = '/workspace/cailianshe-dashboard/autopool/landed.log'
if os.path.exists(lp):
    lines = open(lp, encoding='utf-8').read().splitlines()
    out, seen = [], set()
    for ln in lines:
        if ln.startswith('wc20261021:002364') or ln.startswith('wc20261021:002335'):
            continue                      # 中恒电气/科华数据：HVDC 误判，剔除
        if ln.startswith('wc20261021:002353'):
            if '002353' in seen:
                continue
            seen.add('002353')
        out.append(ln)
    if not any(x.startswith('wc20261021:002353') for x in out):
        out.append('wc20261021:002353')
    open(lp, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print('[landed.log] 已替换 2510883 标的为 002353（杰瑞股份）')

dp = '/workspace/cailianshe-dashboard/autopool/webcheck_decisions.jsonl'
if os.path.exists(dp):
    lines = open(dp, encoding='utf-8').read().splitlines()
    fixed, hit = [], False
    for ln in lines:
        if '"2510883"' in ln and ('002364' in ln or '002335' in ln):
            if not hit:
                fixed.append(json.dumps({
                    'aid': 2510883, 'date': '2026-10-21', 'column': '盘中宝', 'name': '杰瑞股份', 'code': '002353',
                    'decision': 'pool', 'verdict': '原文「逾200亿元」累计订单+「短期内最优」自建燃气电站唯一对应杰瑞股份（2026半年报累计订单超31亿美元约209亿元；7-22公告与国际知名云服务商签14.65亿美元合同；中国经济网：燃气轮机12-18个月交付投产，自建燃气电站成科技巨头最优解）。全网唯一，入池。',
                    'bullet': '摘要：……',
                }, ensure_ascii=False))
                hit = True
            continue
        if '"2510883"' in ln and '002353' in ln:
            hit = True
        fixed.append(ln)
    # 补两条放弃留痕
    for code, name in (('002364', '中恒电气'), ('002335', '科华数据')):
        fixed.append(json.dumps({
            'aid': 2510883, 'date': '2026-10-21', 'column': '盘中宝', 'name': name, 'code': code,
            'decision': 'abandon', 'verdict': '「逾200亿元」与两家实际订单规模（约100-150亿）不符；「短期内最优」指向燃气轮机而非 HVDC；科华数据锚点为行业性表述「2026年为国内厂商出海元年」，无公司特异性。属根据涉及结果划标靶的误判，放弃。',
            'bullet': '摘要：……',
        }, ensure_ascii=False))
    open(dp, 'w', encoding='utf-8').write('\n'.join(fixed) + '\n')
    print('[webcheck_decisions.jsonl] 2510883 决策已修正（杰瑞股份入池 + 两条放弃留痕）')

json.dump(d, open('/tmp/stage4.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('stage4 ok')

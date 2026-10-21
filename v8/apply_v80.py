# -*- coding: utf-8 -*-
"""v8.0 apply：数据窗口 2026-10-11 → 2026-10-18；清空全部股票与文章数据；铁律同步；升版留档"""
import json, re, sys

HTML = '/workspace/cailianshe-dashboard/index.html'
html = open(HTML, encoding='utf-8').read()
m = re.search(r'(<script id="MONITOR_DATA" type="application/json">)(.*?)(</script>)', html, re.S)
d = json.loads(m.group(2))

# ---- 1. 铁律文本：数据起始日 10-11 → 10-18 ----
for c in d.get('ruleCats', []):
    for i, it in enumerate(c.get('items', [])):
        if '2026-10-11' in it and '数据窗口' in it:
            c['items'][i] = it.replace('2026-10-11', '2026-10-18')
            print('[rule]', c['name'], '->', c['items'][i])

# ---- 2. 用户亲定铁律类追加数据起始日条款（最高优先级） ----
top = None
for c in d['ruleCats']:
    if c['name'].startswith('〇、'):
        top = c
        break
if top is not None:
    top['items'].append('【v8.0 新增·2026-10-21 亲定】数据源起始日为 2026-10-18：此前 10-11~10-17 窗口的数据与文章全部清空不作数，'
                        '看板从 10-18 发布的文章起按现行铁律重新抓取、比对、入池；投研池/候选池/文章期次/复盘统计全部从零开始累计。')
    print('[rule] 亲定铁律追加 1 条，共', len(top['items']), '条')

# ---- 3. 清空股票与文章数据（保留：规则/历史/交易日历/告警/指数基准） ----
d['watchlist'] = []
d['candidates'] = []
d['webcheck'] = []
d['abandoned'] = []
d['stocks'] = {}
d['batches'] = []
d['review'] = {}
d['quant'] = dict(d.get('quant') or {})
d['quant']['kline'] = {}          # 个股日K全部清空（随重新入池再嵌）
# quant.index（上证指数日K）保留：市场状态层基准，与数据起始日无关

# ---- 4. 版本与头部 ----
d['version'] = '8.0'
d['lastUpdated'] = '2026-10-21（v8.0 数据源重置：起始日改为 2026-10-18，全部历史数据清空重录）'
d['collectTime'] = '2026-10-21（v8.0 重置待重新采集）'
d['quoteTime'] = '2026-10-21（重置）'
d['period'] = '2026-10-18 起'
d['rebuild'] = {'at': '2026-10-21', 'windowFrom': '2026-10-18', 'articlesTotal': 0,
                'articlesQualified': 0, 'poolCount': 0, 'candCount': 0}

# ---- 5. history 留档 ----
d['history'].append({
    'version': '8.0',
    'time': '2026-10-21',
    'note': 'v8.0 两项升级：①自选股支持手动录入——自选股区新增输入框，输入股票名称或 6 位代码即自动抓取实时行情/日K/分时并入自选，'
            '卡片图表、自选涨幅图、收盘复盘（技术面要点+量化操盘建议）同步展示；已在投研池的标的按池内数据加入，不建重复卡片。'
            '②数据源重置——应用户要求，数据起始日由 2026-10-11 改为 2026-10-18：清空全部历史股票/文章/复盘数据，'
            '从 10-18 发布的文章起按现行铁律（≥280豆/摘要条数=股票数/全网比对/负面排除/宁缺毋滥）重新抓取、比对、入池，'
            'autopool WINDOW_START 与 refresh DATA_WINDOW_START 同步改为 2026-10-18。'
})

new_html = html[:m.start(2)] + json.dumps(d, ensure_ascii=False, indent=1) + html[m.end(2):]
open(HTML, 'w', encoding='utf-8').write(new_html)
print('written: watchlist=%d candidates=%d stocks=%d batches=%d webcheck=%d abandoned=%d history=%d version=%s'
      % (len(d['watchlist']), len(d['candidates']), len(d['stocks']), len(d['batches']),
         len(d['webcheck']), len(d['abandoned']), len(d['history']), d['version']))

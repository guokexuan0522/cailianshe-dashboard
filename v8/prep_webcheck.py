# -*- coding: utf-8 -*-
"""v8.0 收尾准备：①补 2510253 管道缺口（①②两条匿名公告入 webcheck 队列）
②移除「宁德时代」假阳性（标签串误报自动入池，违反铁律②：一篇摘要=一只股票）
同时同步 autopool/pending_webcheck.json 与 index.html MONITOR_DATA.webcheck。
"""
import json
import re

HTML = '/workspace/cailianshe-dashboard/index.html'
WEBCHECK = '/workspace/cailianshe-dashboard/autopool/pending_webcheck.json'
LANDED = '/workspace/cailianshe-dashboard/autopool/landed.log'

AID = '2510253'
TITLE = '【公告全知道】碳化硅+先进封装+第三代半导体+金刚石+AI眼镜！公司Q3净利润环比增长超44倍'
NEW_ITEMS = [
    {
        'aid': AID, 'column': '公告全知道', 'title': TITLE,
        'pub': '2026-10-20 22:06', 'dateIn': '2026-10-21', 'beans': 280,
        'bullet': '①碳化硅+先进封装+第三代半导体+金刚石+AI眼镜！这家公司Q3净利润环比增长超44倍，12英寸碳化硅衬底产品已获得头部客户订单并实现交付；',
        'status': 'pending',
    },
    {
        'aid': AID, 'column': '公告全知道', 'title': TITLE,
        'pub': '2026-10-20 22:06', 'dateIn': '2026-10-21', 'beans': 280,
        'bullet': '②磷化铟+光纤+第三代半导体+商业航天！这家公司Q3净利润同比增长超26倍；',
        'status': 'pending',
    },
]

# ---------- 1. pending_webcheck.json ----------
wc = json.load(open(WEBCHECK, encoding='utf-8'))
have = {(w['aid'], w['bullet'][:12]) for w in wc}
added = 0
for it in NEW_ITEMS:
    if (it['aid'], it['bullet'][:12]) not in have:
        # 插到同 aid 既有条目之后，保持文章内 bullet 顺序
        idx = max(i for i, w in enumerate(wc) if w['aid'] == AID)
        wc.insert(idx + 1 if it['bullet'][0] == '②' else idx, it)
        added += 1
json.dump(wc, open(WEBCHECK, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('[webcheck] 补入 %d 条，队列总数 %d' % (added, len(wc)))

# ---------- 2. index.html MONITOR_DATA ----------
html = open(HTML, encoding='utf-8').read()
m = re.search(r'(<script id="MONITOR_DATA" type="application/json">)(.*?)(</script>)', html, re.S)
d = json.loads(m.group(2))

# 2a. webcheck 补缺口（与文件队列一致；webcheck_resolve 会以此覆盖回写文件）
mw = d.get('webcheck') or []
have_mw = {(w['aid'], w['bullet'][:12]) for w in mw}
added_m = 0
for it in NEW_ITEMS:
    if (it['aid'], it['bullet'][:12]) not in have_mw:
        idx = max(i for i, w in enumerate(mw) if w['aid'] == AID)
        mw.insert(idx + 1 if it['bullet'][0] == '②' else idx, it)
        added_m += 1
d['webcheck'] = mw
print('[html webcheck] 补入 %d 条，队列总数 %d' % (added_m, len(mw)))

# 2b. 移除宁德时代假阳性（watchlist + stocks）
wl = d.get('watchlist') or []
rm_names = [w['name'] for w in wl if w.get('code') == '300750']
d['watchlist'] = [w for w in wl if w.get('code') != '300750']
for k in [k for k, v in (d.get('stocks') or {}).items() if v.get('name') in rm_names or k == 'sz300750']:
    del d['stocks'][k]
print('[html] 移除假阳性：%s；watchlist=%d stocks=%d' % (
    '、'.join(rm_names) or '无', len(d['watchlist']), len(d['stocks'])))

# 2c. lastUpdated 同步重建态
d['lastUpdated'] = ('2026-10-21（v8.0 清库重建：起始日 2026-10-18；已重新抓取 10-18~10-21 文章 29 篇，'
                    'AI 全网比对 64+2 条线索研判完毕，落地中）')

new_html = html[:m.start(2)] + json.dumps(d, ensure_ascii=False, indent=1) + html[m.end(2):]
open(HTML, 'w', encoding='utf-8').write(new_html)
print('[html] 已写回')

# ---------- 3. landed.log 移除宁德时代 ----------
lines = [ln.strip() for ln in open(LANDED, encoding='utf-8') if ln.strip()]
kept = [ln for ln in lines if not ln.endswith(':300750')]
open(LANDED, 'w', encoding='utf-8').write('\n'.join(kept) + ('\n' if kept else ''))
print('[landed.log] 移除 %d 行，剩余 %d 行' % (len(lines) - len(kept), len(kept)))

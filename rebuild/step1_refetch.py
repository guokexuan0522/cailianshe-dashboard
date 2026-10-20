#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STEP 1（v6.3 重建）：从 2026-10-11 起重新抓取全部文章，不看 seen 缓存，全量重扫。
输出：rebuild/articles_raw.json —— 每篇含 aid/title/真实分类/发布时间/豆数/摘要/related_stock
铁律：未达 280 豆只登记分类与豆数，不抓摘要（保持"不做任何抓取"）。"""
import datetime, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import refresh

WINDOW = '2026-10-11'
PAGES = int(os.environ.get('PAGES', '6'))     # 6×20=120 篇/栏目，足够覆盖 10 天
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'articles_raw.json')

rows = []
seen_aid = set()
for ctype, (parent, beans_min) in refresh.CLS_COLUMNS.items():
    last_time = 0
    n_col = 0
    for pg in range(PAGES):
        try:
            r = refresh.cls_api('/featured/v1/column/detail/load', last_time=last_time, type=ctype, rn=20)
        except Exception as e:
            print('  拉取失败 %s(%s): %s' % (parent, ctype, e))
            break
        arts = refresh._cls_articles_of(r)
        if not arts:
            break
        oldest = None
        for a in arts:
            aid = a.get('id')
            if not aid or aid in seen_aid:
                continue
            title = (a.get('title') or '').strip()
            ct = a.get('ctime') or 0
            if ct:
                oldest = ct if oldest is None else min(oldest, ct)
                ds = datetime.datetime.fromtimestamp(ct).strftime('%Y-%m-%d')
                if ds < WINDOW:
                    continue
            else:
                ds = ''
            seen_aid.add(aid)
            rows.append({
                'aid': aid, 'title': title,
                'date': ds,
                'ctime': ct,
                'column': refresh.real_column(title, parent),
                'parent': parent, 'ctype': ctype,
                'brief': (a.get('brief') or '').strip(),
                'related_stock': a.get('related_stock') or [],
            })
            n_col += 1
        if oldest and datetime.datetime.fromtimestamp(oldest).strftime('%Y-%m-%d') < WINDOW:
            break
        if len(arts) < 20:
            break
        last_time = arts[-1].get('ctime') or 0
        time.sleep(0.35)
    print('  %-10s(type=%s) 窗口内 %d 篇' % (parent, ctype, n_col))

print('\n合计 %d 篇（窗口 >= %s），开始逐篇核价' % (len(rows), WINDOW))

# 逐篇取价（SSR articlePrice）—— 未达标只登记分类
ok = 0
for i, a in enumerate(rows):
    if i and i % 20 == 0:
        print('  ...核价 %d/%d' % (i, len(rows)))
        json.dump(rows, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    d = None
    for attempt in range(3):
        try:
            d = refresh.cls_article_detail(a['aid'])
        except Exception:
            d = None
        if d:
            break
        time.sleep(1.2 * (attempt + 1))
    if not d:
        a['beans'] = None
        a['price_err'] = 'SSR 详情失败'
        continue
    a['isFree'] = bool(d.get('isFree'))
    p = d.get('articlePrice')
    a['beans'] = 0 if a['isFree'] else (int(round(float(p) * 10)) if p is not None else None)
    if d.get('brief'):
        a['brief_full'] = d.get('brief')
    ct = d.get('ctime') or a.get('ctime')
    if ct:
        a['ctime'] = ct
        a['date'] = datetime.datetime.fromtimestamp(ct).strftime('%Y-%m-%d')
        a['pub'] = datetime.datetime.fromtimestamp(ct).strftime('%Y-%m-%d %H:%M')
    ok += 1
    time.sleep(0.4)

json.dump(rows, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
from collections import Counter
print('\n核价完成 %d/%d，写入 %s' % (ok, len(rows), OUT))
print('分类分布:', dict(Counter(r['column'] for r in rows).most_common()))
print('豆数分布:', dict(Counter(str(r.get('beans')) for r in rows).most_common()))

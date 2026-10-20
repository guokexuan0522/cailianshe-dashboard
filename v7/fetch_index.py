#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v7.0 步骤 C：拉取基准指数（上证/沪深300/创业板）320 根日线，用于市场状态识别与相对强度。"""
import json, os, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
OUT = os.path.join(ROOT, 'ref', 'index320.json')
IDX = {'sh000001': '上证指数', 'sh000300': '沪深300', 'sz399006': '创业板指'}

res = {}
if os.path.exists(OUT):
    try:
        res = json.load(open(OUT, encoding='utf-8'))
    except Exception:
        res = {}

for code, name in IDX.items():
    url = ('https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get'
           '?param=%s,day,,,320,qfq' % code)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    d = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
    node = (d.get('data') or {}).get(code) or {}
    arr = node.get('qfqday') or node.get('day') or []
    bars = [[b[0], float(b[1]), float(b[2]), float(b[3]), float(b[4]), float(b[5] or 0)]
            for b in arr if len(b) >= 6]
    res[code] = {'name': name, 'bars': bars}
    print('%-8s %-8s %d 根  %s ~ %s' % (code, name, len(bars), bars[0][0], bars[-1][0]))

json.dump(res, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('写入 %s (%.0f KB)' % (OUT, os.path.getsize(OUT) / 1024))

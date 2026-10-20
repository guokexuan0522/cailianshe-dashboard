#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v7.0 步骤 A：拉取 320 根日K，写入 ref/kline320.json（供量化校准使用）。

背景：母版内 stocks[*].kline 仅 80 根，滚动回测样本仅 10 点，概率全部塌陷为 50%。
校准需要 ≥250 根才能产出 150+ 历史观测点/只，38 只池化后 ~5000+ 观测。
页面展示仍用 80 根（渲染轻），量化计算用 320 根（样本足）。
"""
import json, os, re, time, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
OUT = os.path.join(ROOT, 'ref', 'kline320.json')
N = 320

def load_codes():
    h = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    i = h.index('<script id="MONITOR_DATA" type="application/json">')
    j = h.index('</script>', i)
    D = json.loads(h[i + len('<script id="MONITOR_DATA" type="application/json">'):j])
    codes = []
    for w in D['watchlist'] + D['candidates']:
        codes.append((w['q'], w['name']))
    return codes, D

def fetch(q, n=N, retry=3):
    url = ('https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get'
           '?param=%s,day,,,%d,qfq' % (q, n))
    last = None
    for t in range(retry):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.loads(r.read().decode('utf-8'))
            node = (d.get('data') or {}).get(q) or {}
            arr = node.get('qfqday') or node.get('day') or []
            out = []
            for b in arr:
                if len(b) < 6:
                    continue
                out.append([b[0], float(b[1]), float(b[2]), float(b[3]),
                            float(b[4]), float(b[5] or 0)])
            return out
        except Exception as e:
            last = e
            time.sleep(1.2 * (t + 1))
    raise RuntimeError('%s 拉取失败: %s' % (q, last))

def main():
    codes, D = load_codes()
    res = {}
    if os.path.exists(OUT):
        try:
            res = json.load(open(OUT, encoding='utf-8'))
        except Exception:
            res = {}
    ok = fail = 0
    for q, name in codes:
        try:
            bars = fetch(q)
            if len(bars) < 120:
                print('%-10s %-6s 仅 %d 根（跳过，保留旧值）' % (name, q, len(bars)))
                fail += 1
                continue
            res[q] = {'name': name, 'bars': bars}
            ok += 1
            print('%-10s %-6s %d 根  %s ~ %s' % (name, q, len(bars), bars[0][0], bars[-1][0]))
        except Exception as e:
            print('%-10s %-6s ERROR %s' % (name, q, e))
            fail += 1
    json.dump(res, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('\n完成 ok=%d fail=%d  写入 %s (%.0f KB)' % (ok, fail, OUT, os.path.getsize(OUT) / 1024))

if __name__ == '__main__':
    main()

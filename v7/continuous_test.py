# -*- coding: utf-8 -*-
"""假设 D：已验证因子的连续化（不是新因子，是把 v7.0 已验证的 lowRsi/lowPos
从二进制 +3pp 改为连续分档）。
预注册：分档上涨率必须在训练段与测试段同向单调，才允许连续化。"""
import json, os, sys
import statistics as st

ROOT = '/workspace/cailianshe-dashboard'
sys.path.insert(0, ROOT)
import quant as Q

klmap = json.load(open(os.path.join(ROOT, 'ref', 'kline320.json'), encoding='utf-8'))

def norm_with_dates(kline):
    out = []
    for b in kline or []:
        if len(b) < 6:
            continue
        try:
            out.append((b[0], float(b[1]), float(b[3]), float(b[4]), float(b[2]), float(b[5] or 0)))
        except (TypeError, ValueError):
            continue
    return out

H = 10
rows = []
for q, node in klmap.items():
    bars_d = norm_with_dates(node['bars'])
    bars = [(o, h, l, c, v) for (_d, o, h, l, c, v) in bars_d]
    if len(bars) < 140:
        continue
    ind = Q.build_indicators(bars)
    for i in range(70, len(bars) - H):
        if any(ind[k][i] is None for k in Q.NEED):
            continue
        c = [b[3] for b in bars]
        seg = bars[max(0, i - 19):i + 1]
        hi20 = max(x[3] for x in seg); lo20 = min(x[3] for x in seg)
        rows.append({'date': bars_d[i][0],
                     'rsi': ind['rsi'][i],
                     'pos': (c[i] - lo20) / (hi20 - lo20) if hi20 > lo20 else 0.5,
                     'up': 1 if bars[i + H][3] > c[i] else 0})

rows.sort(key=lambda r: r['date'])
dates = sorted(set(r['date'] for r in rows))
split_date = dates[int(len(dates) * 0.7)]
train = [r for r in rows if r['date'] < split_date]
test = [r for r in rows if r['date'] >= split_date]
base_tr = sum(r['up'] for r in train) / len(train)
base_te = sum(r['up'] for r in test) / len(test)
print('观测 %d | 训练 %d | 测试 %d | 切分日 %s' % (len(rows), len(train), len(test), split_date))
print('基准：训练 %.1f%% | 测试 %.1f%%\n' % (base_tr * 100, base_te * 100))

def check(key, bins):
    print('%s 分档（Q1低→Q5高）:' % key)
    ok = True
    dirs = []
    for name, rs, base in (('训练', train, base_tr), ('测试', test, base_te)):
        line, vals = [], []
        for lo, hi in bins:
            seg = [r['up'] for r in rs if lo <= r[key] < hi]
            if len(seg) >= 25:
                v = sum(seg) / len(seg) * 100
                line.append('%5.1f(n=%d)' % (v, len(seg)))
                vals.append(v)
            else:
                line.append('  —  ')
        diffs = [vals[i+1] - vals[i] for i in range(len(vals)-1)]
        d = 'up' if all(x > 1.0 for x in diffs) else ('down' if all(x < -1.0 for x in diffs) else 'none')
        dirs.append(d)
        print('  %s（基准%.1f%%）: %s  单调:%s' % (name, base * 100, '  '.join(line), d))
    same = dirs[0] in ('up', 'down') and dirs[0] == dirs[1]
    print('  → %s\n' % ('✅两段同向（可连续化）' if same else '❌不同向（保持二进制）'))
    return same

print('=' * 90)
print('假设 D1：RSI 连续化（当前二进制：RSI<45 → +3pp）')
print('=' * 90)
check('rsi', [(0, 30), (30, 40), (40, 45), (45, 55), (55, 70), (70, 101)])
print('=' * 90)
print('假设 D2：20 日区间位置连续化（当前二进制：pos<0.2 → +3pp）')
print('=' * 90)
check('pos', [(0, 0.05), (0.05, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)])
print('=' * 90)
print('假设 D3：deep 连续化加密（当前 5 档：≤-10/-7/-5/-3/其余）')
print('=' * 90)
# devE12 需要 indicators，重新取
rows2 = []
for q, node in klmap.items():
    bars_d = norm_with_dates(node['bars'])
    bars = [(o, h, l, c, v) for (_d, o, h, l, c, v) in bars_d]
    if len(bars) < 140:
        continue
    ind = Q.build_indicators(bars)
    for i in range(70, len(bars) - H):
        if any(ind[k][i] is None for k in Q.NEED):
            continue
        c = [b[3] for b in bars]
        if not ind['e12'][i]:
            continue
        rows2.append({'date': bars_d[i][0],
                      'devE12': c[i] / ind['e12'][i] - 1,
                      'up': 1 if bars[i + H][3] > c[i] else 0})
rows2.sort(key=lambda r: r['date'])
train2 = [r for r in rows2 if r['date'] < split_date]
test2 = [r for r in rows2 if r['date'] >= split_date]
print('（devE12 观测 %d | 训练 %d | 测试 %d）' % (len(rows2), len(train2), len(test2)))
for name, rs, base in (('训练', train2, None), ('测试', test2, None)):
    line, vals = [], []
    for lo, hi in [(-9, -0.12), (-0.12, -0.10), (-0.10, -0.08), (-0.08, -0.07), (-0.07, -0.05), (-0.05, -0.03), (-0.03, 9)]:
        seg = [r['up'] for r in rs if lo <= r['devE12'] < hi]
        if len(seg) >= 25:
            v = sum(seg) / len(seg) * 100
            line.append('%5.1f(n=%d)' % (v, len(seg)))
            vals.append((lo, v))
        else:
            line.append('  —  ')
    b = sum(r['up'] for r in rs) / len(rs) * 100
    print('  %s（基准%.1f%%）: %s' % (name, b, '  '.join(line)))

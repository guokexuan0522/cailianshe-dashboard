#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v7.0 步骤 E：诚实检验 —— 哪些信号在样本外真的成立。

结论将直接写进 quant.py 的注释与铁律，不美化。
"""
import json, os, sys, statistics as st
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
sys.path.insert(0, ROOT)
import quant as Q

kl = json.load(open(os.path.join(ROOT, 'ref', 'kline320.json'), encoding='utf-8'))
rows = []
for q, node in kl.items():
    b = Q.norm_bars(node['bars'])
    if len(b) < 200:
        continue
    ind = Q.build_indicators(b)
    for i in range(70, len(b) - 10):
        if ind['e12'][i] is None:
            continue
        seg = b[max(0, i - 19):i + 1]
        hi20, lo20 = max(x[3] for x in seg), min(x[3] for x in seg)
        rows.append({
            'date': node['bars'][i][0], 'q': q,
            'devE12': (b[i][3] - ind['e12'][i]) / ind['e12'][i],
            'past10': b[i][3] / b[i - 10][3] - 1,
            'rsi': ind['rsi'][i],
            'pos': (b[i][3] - lo20) / (hi20 - lo20) if hi20 > lo20 else 0.5,
            'atrp': ind['atrp'][i],
            'up': 1 if b[i + 10][3] > b[i][3] else 0,
        })
rows.sort(key=lambda r: r['date'])
split = int(len(rows) * 0.7)
tr, te = rows[:split], rows[split:]
print('训练 %d (%s ~ %s)' % (len(tr), tr[0]['date'], tr[-1]['date']))
print('测试 %d (%s ~ %s)\n' % (len(te), te[0]['date'], te[-1]['date']))
print('训练集上涨率 %.1f%%   测试集上涨率 %.1f%%\n'
      % (st.mean(r['up'] for r in tr) * 100, st.mean(r['up'] for r in te) * 100))


def check(key, cuts, name, invert=False):
    print('【%s】' % name)
    print('  分档          训练上涨率   测试上涨率   样本外变化')
    for lo, hi in cuts:
        a = [r['up'] for r in tr if lo <= r[key] < hi]
        b = [r['up'] for r in te if lo <= r[key] < hi]
        if len(a) < 60 or len(b) < 40:
            continue
        pa, pb = st.mean(a) * 100, st.mean(b) * 100
        flag = ''
        if (pa > 50 and pb > 50) or (pa < 50 and pb < 50):
            flag = '同向'
        else:
            flag = '★翻转'
        print('  %6.3f~%6.3f  %6.1f%%(n=%4d) %6.1f%%(n=%4d)   %s'
              % (lo, hi, pa, len(a), pb, len(b), flag))
    print()


check('devE12', [(-9, -0.05), (-0.05, -0.02), (-0.02, 0.0), (0.0, 0.02), (0.02, 0.05), (0.05, 9)],
      '距EXPMA12偏离（主变量候选）')
check('past10', [(-9, -0.1), (-0.1, -0.03), (-0.03, 0.03), (0.03, 0.1), (0.1, 9)],
      '过去10日涨幅')
check('rsi', [(0, 35), (35, 45), (45, 55), (55, 65), (65, 101)], 'RSI')
check('pos', [(0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)], '20日区间位置')
check('atrp', [(0, 3), (3, 4.5), (4.5, 6.5), (6.5, 9), (9, 100)], 'ATR%（波动）')

# 反向组合：深跌 + 低 RSI
print('【组合信号：深跌(devE12<-3%) + 低RSI(<45)】')
for name, cond in [
    ('深跌且低RSI', lambda r: r['devE12'] < -0.03 and r['rsi'] < 45),
    ('深跌且高RSI', lambda r: r['devE12'] < -0.03 and r['rsi'] >= 45),
    ('暴涨(>+3%)', lambda r: r['devE12'] > 0.03),
    ('暴涨且高RSI', lambda r: r['devE12'] > 0.03 and r['rsi'] > 65),
    ('低位(pos<0.2)', lambda r: r['pos'] < 0.2),
    ('高位(pos>0.8)', lambda r: r['pos'] > 0.8),
]:
    a = [r['up'] for r in tr if cond(r)]
    b = [r['up'] for r in te if cond(r)]
    if len(a) < 30 or len(b) < 30:
        print('  %-14s 样本不足 (训练%d 测试%d)' % (name, len(a), len(b)))
        continue
    print('  %-14s 训练 %.1f%%(n=%4d) → 测试 %.1f%%(n=%4d)  %s'
          % (name, st.mean(a) * 100, len(a), st.mean(b) * 100, len(b),
             '同向' if (st.mean(a) - 0.5) * (st.mean(b) - 0.5) > 0 else '★翻转'))

# 按日聚合：日度横截面上涨率与指数状态
print('\n【日度：指数距EXPMA60 偏离 vs 全池当日未来10日上涨率】')
idx = json.load(open(os.path.join(ROOT, 'ref', 'index320.json'), encoding='utf-8'))
idx_raw = idx['sh000001']['bars']
idx_map = {b[0]: i for i, b in enumerate(idx_raw)}
ic = [b[3] for b in Q.norm_bars(idx_raw)]
e60 = Q.ema(ic, 60)
byday = defaultdict(list)
for r in rows:
    byday[r['date']].append(r['up'])
day = []
for d, ups in byday.items():
    if d in idx_map and len(ups) >= 15 and e60[idx_map[d]]:
        mid = ic[idx_map[d]] / e60[idx_map[d]] - 1
        day.append((d, mid, st.mean(ups)))
day.sort()
print('  共 %d 个交易日' % len(day))
dsplit = int(len(day) * 0.7)
for label, seg in [('训练段', day[:dsplit]), ('测试段', day[dsplit:])]:
    ss = sorted(seg, key=lambda x: x[1])
    n = len(ss)
    print('  %s（%s ~ %s）：' % (label, ss[0][0], ss[-1][0]) if ss else label)
    for k in range(3):
        part = ss[k * n // 3:(k + 1) * n // 3]
        if part:
            print('    mid %+6.2f%%~%+6.2f%%  上涨率 %.1f%%  n=%d'
                  % (part[0][1] * 100, part[-1][1] * 100, st.mean(x[2] for x in part) * 100, len(part)))

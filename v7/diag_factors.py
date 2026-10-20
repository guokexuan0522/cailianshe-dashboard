#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断：测每一个因子的单因子预测力（IC / 分组收益），看是不是权重方向错了。"""
import json, os, sys
import statistics as st

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
sys.path.insert(0, ROOT)
import quant as Q

klmap = json.load(open(os.path.join(ROOT, 'ref', 'kline320.json'), encoding='utf-8'))
H = 10

rows = []
for q, node in klmap.items():
    bars = Q.norm_bars(node['bars'])
    if len(bars) < 140:
        continue
    ind = Q.build_indicators(bars)
    for i in range(60, len(bars) - H):
        if any(ind[k][i] is None for k in Q.NEED):
            continue
        d = Q.factor_scores(bars[i], i, ind)
        fwd = bars[i + H][3] / bars[i][3] - 1
        rows.append((q, i, d, fwd))

print('总观测 %d' % len(rows))
print('基准 10日上涨率 %.1f%%  平均收益 %+.2f%%\n'
      % (sum(1 for r in rows if r[3] > 0) / len(rows) * 100,
         st.mean(r[3] for r in rows) * 100))


def report(key, label):
    xs = [r[2][key] for r in rows]
    ys = [r[3] for r in rows]
    # Spearman rank IC（近似：用排序后皮尔逊）
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        rk = [0] * len(v)
        for pos, idx in enumerate(order):
            rk[idx] = pos
        return rk
    rx, ry = rank(xs), rank(ys)
    mx, my = st.mean(rx), st.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    ic = num / den if den else 0
    # 5 分组收益
    idx = sorted(range(len(xs)), key=lambda i: xs[i])
    n = len(idx)
    q5 = []
    for b in range(5):
        seg = idx[b * n // 5:(b + 1) * n // 5]
        q5.append((st.mean(xs[k] for k in seg),
                   sum(1 for k in seg if ys[k] > 0) / len(seg) * 100,
                   st.mean(ys[k] for k in seg) * 100))
    print('%-10s %-28s IC=%+.4f' % (key, label, ic))
    print('           五分组(低→高)：' + ' | '.join(
        '分%+5.1f→涨%.0f%%/收%+.1f%%' % (a, p, r) for a, p, r in q5))
    return ic


for k in Q.WEIGHTS:
    report(k, '')
report('__comp__', '') if False else None
print('-' * 90)
# 综合分
comp = []
for r in rows:
    comp.append((Q.composite(r[2]), r[3]))
xs = [c[0] for c in comp]
ys = [c[1] for c in comp]
idx = sorted(range(len(xs)), key=lambda i: xs[i])
n = len(idx)
print('综合分 五分组（低→高）：')
for b in range(5):
    seg = idx[b * n // 5:(b + 1) * n // 5]
    print('  第%d组 分%+6.1f~%+6.1f 上涨%.1f%% 平均收益%+.2f%%'
          % (b + 1, min(xs[k] for k in seg), max(xs[k] for k in seg),
             sum(1 for k in seg if ys[k] > 0) / len(seg) * 100,
             st.mean(ys[k] for k in seg) * 100))

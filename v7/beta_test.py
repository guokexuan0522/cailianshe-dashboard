# -*- coding: utf-8 -*-
"""假设 C：Beta 因子（滚动 60 日日收益对指数回归，只用当日及以前数据）。
理论依据：10 日方向第一决定权在大盘状态（状态层已验证）。当状态层看多
（如超跌反弹区）时，高 Beta 个股应更大概率跟随指数上涨——这是「状态×个股」
交互，不是无条件因子。
预注册规则：主效应或交互效应必须两段同向才允许纳入，且修正幅度 ≤3pp。
"""
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

idx_d = norm_with_dates(json.load(open(os.path.join(ROOT, 'ref', 'index320.json'), encoding='utf-8'))['sh000001']['bars'])
idx_closes = [b[3] for b in idx_d]
idx_dates = [d[0] for d in idx_d]
idx_ret = {}
for i in range(1, len(idx_closes)):
    idx_ret[idx_dates[i]] = idx_closes[i] / idx_closes[i-1] - 1
H = 10

# 指数状态（dev × slope，与线上同规则）
e60 = Q.ema(idx_closes, 60)
idx_state = {}
for i in range(70, len(idx_closes)):
    if not e60[i] or not e60[i-5]:
        continue
    dev = idx_closes[i] / e60[i] - 1
    slope = e60[i] / e60[i-5] - 1
    deep, down = dev <= -0.025, slope < -0.006
    idx_state[idx_dates[i]] = '超跌反弹区' if (deep and down) else ('下跌中继区' if deep else '中性整理区')

BETA_WIN = 60
rows = []
for q, node in klmap.items():
    bars_d = norm_with_dates(node['bars'])
    bars = [(o, h, l, c, v) for (_d, o, h, l, c, v) in bars_d]
    if len(bars) < 200:
        continue
    ind = Q.build_indicators(bars)
    closes = [b[3] for b in bars]
    for i in range(BETA_WIN + 10, len(bars) - H):
        if any(ind[k][i] is None for k in Q.NEED):
            continue
        d = bars_d[i][0]
        # 滚动 beta：过去 60 日个股日收益 ~ 指数日收益（只用 i 当日及以前）
        xs, ys = [], []
        ok = True
        for j in range(i - BETA_WIN, i):
            rd, ri = bars_d[j][0], bars_d[j][0]
            if rd not in idx_ret or j < 1:
                ok = False; break
            ys.append(closes[j] / closes[j-1] - 1)
            xs.append(idx_ret[rd])
        if not ok or len(xs) < 40:
            continue
        mx, my = st.mean(xs), st.mean(ys)
        var = sum((x - mx) ** 2 for x in xs)
        if var <= 0:
            continue
        beta = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / var
        rows.append({'date': d, 'beta': beta, 'state': idx_state.get(d, '中性整理区'),
                     'up': 1 if closes[i + H] > closes[i] else 0})

rows.sort(key=lambda r: r['date'])
dates = sorted(set(r['date'] for r in rows))
split_date = dates[int(len(dates) * 0.7)]
train = [r for r in rows if r['date'] < split_date]
test = [r for r in rows if r['date'] >= split_date]
base_tr = sum(r['up'] for r in train) / len(train)
base_te = sum(r['up'] for r in test) / len(test)
print('观测 %d | 训练 %d | 测试 %d | 切分日 %s' % (len(rows), len(train), len(test), split_date))
print('基准：训练 %.1f%% | 测试 %.1f%%' % (base_tr * 100, base_te * 100))
print('Beta 分布：训练 %.2f~%.2f | 测试 %.2f~%.2f' % (
    min(r['beta'] for r in train), max(r['beta'] for r in train),
    min(r['beta'] for r in test), max(r['beta'] for r in test)))

print()
print('=' * 90)
print('C1 主效应：Beta 五档 → 10 日上涨率')
print('=' * 90)
qs = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
btrain = sorted(r['beta'] for r in train)
btest = sorted(r['beta'] for r in test)
def edges(vals):
    return [vals[min(int(len(vals) * q), len(vals) - 1)] for q in qs]
etr, ete = edges(btrain), edges(btest)
for name, rs, es, base in (('训练', train, etr, base_tr), ('测试', test, ete, base_te)):
    line = []
    for k in range(5):
        seg = [r['up'] for r in rs if es[k] <= r['beta'] < es[k+1] or (k == 4 and r['beta'] >= es[4])]
        line.append('%5.1f(n=%d)' % (sum(seg)/len(seg)*100, len(seg)) if len(seg) >= 20 else '  —  ')
    print('%s（基准%.1f%%）: %s' % (name, base*100, '  '.join(line)))

print()
print('=' * 90)
print('C2 交互：状态层看多区（超跌反弹区/下跌中继区）内，Beta 高低 → 上涨率')
print('=' * 90)
for name, rs, base in (('训练', train, base_tr), ('测试', test, base_te)):
    print('%s段:' % name)
    for state in ('超跌反弹区', '下跌中继区', '中性整理区'):
        seg = [r for r in rs if r['state'] == state]
        if len(seg) < 30:
            print('  %-6s n=%d（样本不足，跳过）' % (state, len(seg)))
            continue
        bs = sorted(seg, key=lambda r: r['beta'])
        half = len(bs) // 2
        lo, hi = bs[:half], bs[half:]
        plo = sum(r['up'] for r in lo) / len(lo) * 100
        phi = sum(r['up'] for r in hi) / len(hi) * 100
        print('  %-6s n=%4d  低Beta %.1f%%  高Beta %.1f%%  差 %+.1fpp' % (
            state, len(seg), plo, phi, phi - plo))
    print()

print('=' * 90)
print('C3 只在中性整理区（97% 时间）检验 Beta 主效应（样本最足）')
print('=' * 90)
for name, rs, base in (('训练', train, base_tr), ('测试', test, base_te)):
    seg = [r for r in rs if r['state'] == '中性整理区']
    bs = sorted(seg, key=lambda r: r['beta'])
    qs5 = [bs[min(int(len(bs)*q), len(bs)-1)]['beta'] for q in [0, .2, .4, .6, .8, 1.0]]
    line = []
    for k in range(5):
        s = [r['up'] for r in seg if qs5[k] <= r['beta'] < qs5[k+1] or (k == 4 and r['beta'] >= qs5[4])]
        line.append('%5.1f(n=%d)' % (sum(s)/len(s)*100, len(s)) if len(s) >= 20 else '  —  ')
    print('%s（基准%.1f%%）: %s' % (name, base*100, '  '.join(line)))

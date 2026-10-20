# -*- coding: utf-8 -*-
"""颗粒度诚实检验（v7.2 前置实验）。
两个预注册假设，均用「训练段定参 → 测试段验效」，时间不重叠：

  假设 A：组合超买共振——单个因子无效，但多个「极端超买」条件同时成立时，
           10 日上涨率显著低于基准（且两段同向）。若成立，可纳入负向修正，
           把「超跌」与「超买」股票的概率真正拉开。
  假设 B：状态层同维度细化——不引入新因子，只把已验证的 (dev, slope) 二维
           从 3 档切到 6 档（dev 三档 × slope 两档），训练段定各档胜率，
           测试段比 Brier。只有不差于 3 档才允许上线。

铁律：任何一假设两段不同向，一律不纳入，宁可不改。
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
idx = [(o, h, l, c, v) for (_d, o, h, l, c, v) in idx_d]
idx_closes = [b[3] for b in idx]
H = 10

idx_past10 = {}
for i in range(10, len(idx_closes)):
    idx_past10[idx_d[i][0]] = idx_closes[i] / idx_closes[i - 10] - 1

# ---------- 构建个股观测（带真实日期） ----------
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
        f = {}
        f['past10'] = c[i] / c[i - 10] - 1
        f['relIdx'] = f['past10'] - idx_past10.get(bars_d[i][0], 0.0)
        f['emaAlign'] = ind['e12'][i] / ind['e50'][i] - 1
        f['devE50'] = c[i] / ind['e50'][i] - 1
        f['bollPos'] = ind['pb'][i]
        f['up'] = 1 if bars[i + H][3] > c[i] else 0
        f['date'] = bars_d[i][0]
        rows.append(f)

rows.sort(key=lambda r: r['date'])
dates = sorted(set(r['date'] for r in rows))
split_date = dates[int(len(dates) * 0.7)]
train = [r for r in rows if r['date'] < split_date]
test = [r for r in rows if r['date'] >= split_date]
base_tr = sum(r['up'] for r in train) / len(train)
base_te = sum(r['up'] for r in test) / len(test)
print('观测 %d | 训练 %d | 测试 %d | 切分日 %s' % (len(rows), len(train), len(test), split_date))
print('基准：训练 %.1f%% | 测试 %.1f%%\n' % (base_tr * 100, base_te * 100))

# ============================================================
print('=' * 96)
print('假设 A：组合超买共振（5 个「极端超买」条件同时成立个数 → 10 日上涨率）')
print('=' * 96)
HOT = [('past10>6%', lambda f: f['past10'] > 0.06),
       ('relIdx>9%', lambda f: f['relIdx'] > 0.09),
       ('emaAlign>3%', lambda f: f['emaAlign'] > 0.03),
       ('devE50>6%', lambda f: f['devE50'] > 0.06),
       ('bollPos>0.85', lambda f: f['bollPos'] > 0.85)]

def hot_score(f):
    return sum(1 for _, fn in HOT if fn(f))

for seg, name, base in ((train, '训练', base_tr), (test, '测试', base_te)):
    print('%s段（基准 %.1f%%）:' % (name, base * 100))
    for s in range(0, 6):
        seg_s = [r for r in seg if hot_score(r) == s]
        if not seg_s:
            print('  %d 个条件: (无观测)' % s)
            continue
        up = sum(r['up'] for r in seg_s) / len(seg_s)
        print('  %d 个条件: n=%4d  上涨率 %5.1f%%  (较基准 %+.1fpp)' % (s, len(seg_s), up * 100, (up - base) * 100))
    print()

# 两段同向性：分数越高上涨率是否一致走低（有效组至少 3 个）
def hot_mono(rs, base):
    pts = []
    for s in range(0, 6):
        seg_s = [r['up'] for r in rs if hot_score(r) == s]
        if len(seg_s) >= 25:
            pts.append((s, sum(seg_s) / len(seg_s) * 100))
    return pts

ptr, pte = hot_mono(train, base_tr), hot_mono(test, base_te)
def mono_dir(pts):
    if len(pts) < 3:
        return None
    diffs = [pts[i+1][1] - pts[i][1] for i in range(len(pts)-1)]
    if all(d > 1.0 for d in diffs): return 'up'
    if all(d < -1.0 for d in diffs): return 'down'
    return 'none'
dtr, dte = mono_dir(ptr), mono_dir(pte)
print('训练段单调: %s | 测试段单调: %s → %s' % (
    dtr or '?', dte or '?',
    '✅两段同向（可纳入负向修正）' if dtr in ('up','down') and dtr == dte else '❌不同向或无单调（不得纳入）'))

# ============================================================
print()
print('=' * 96)
print('假设 B：状态层同维度细化 3 档 → 6 档（dev 三档 × slope 两档，训练段定参，测试段比 Brier）')
print('=' * 96)

e60 = Q.ema(idx_closes, 60)
DEV_DEEP, SLOPE_DN = -0.025, -0.006

def band6(i):
    dev = idx_closes[i] / e60[i] - 1
    slope = e60[i] / e60[i - 5] - 1
    dv = 0 if dev <= DEV_DEEP else (1 if dev <= 0.025 else 2)
    sl = 0 if slope < SLOPE_DN else 1
    return (dv, sl), dev, slope

def band3(i):
    dev = idx_closes[i] / e60[i] - 1
    slope = e60[i] / e60[i - 5] - 1
    deep = dev <= DEV_DEEP
    down = slope < SLOPE_DN
    return ('超跌反弹区' if (deep and down) else ('下跌中继区' if deep else '中性整理区'))

# 指数层面：每个交易日一个状态 + 未来 10 日指数涨跌
idx_recs = []
for i in range(70, len(idx_closes) - H):
    if not e60[i] or not e60[i-5]:
        continue
    b6, dev, slope = band6(i)
    idx_recs.append({'date': idx_d[i][0], 'b6': b6, 'b3': band3(i),
                     'up': 1 if idx_closes[i+H] > idx_closes[i] else 0})
idx_recs.sort(key=lambda r: r['date'])
isplit = idx_recs[int(len(idx_recs) * 0.7)]['date']
itr = [r for r in idx_recs if r['date'] < isplit]
ite = [r for r in idx_recs if r['date'] >= isplit]
print('指数观测 %d | 训练 %d | 测试 %d | 切分日 %s' % (len(idx_recs), len(itr), len(ite), isplit))
print('指数基准：训练 %.1f%% | 测试 %.1f%%' % (
    sum(r['up'] for r in itr)/len(itr)*100, sum(r['up'] for r in ite)/len(ite)*100))

def shrink_table(recs, keyfn, base, k=400.0):
    """训练段各档原始胜率 + 向基准收缩（与线上 STATE_SHRINK 同规则）。"""
    tab = {}
    groups = {}
    for r in recs:
        groups.setdefault(keyfn(r), []).append(r['up'])
    for g, ups in groups.items():
        n = len(ups)
        p = sum(ups) / n
        w = n / (n + k)
        tab[g] = p * w + base * (1 - w)
    return tab

base_itr = sum(r['up'] for r in itr) / len(itr)
tab6 = shrink_table(itr, lambda r: r['b6'], base_itr)
tab3 = shrink_table(itr, lambda r: r['b3'], base_itr)

print('\n训练段各档（收缩后概率）:')
for g in sorted(tab3):
    n3 = sum(1 for r in itr if r['b3'] == g)
    print('  3档 %-6s n=%4d  p=%.3f' % (g, n3, tab3[g]))
for g in sorted(tab6):
    n6 = sum(1 for r in itr if r['b6'] == g)
    print('  6档 dev%d/slope%d n=%4d  p=%.3f' % (g[0], g[1], n6, tab6[g]))

# 测试段各档原始胜率（只看，不用于定参）
print('\n测试段各档原始上涨率（验效）:')
for g in sorted(tab3):
    seg = [r['up'] for r in ite if r['b3'] == g]
    if seg: print('  3档 %-6s n=%4d  %5.1f%%' % (g, len(seg), sum(seg)/len(seg)*100))
for g in sorted(tab6):
    seg = [r['up'] for r in ite if r['b6'] == g]
    if seg: print('  6档 dev%d/slope%d n=%4d  %5.1f%%' % (g[0], g[1], len(seg), sum(seg)/len(seg)*100))

def brier(recs, tab, keyfn, default):
    err = 0.0
    for r in recs:
        p = tab.get(keyfn(r), default)
        err += (p - r['up']) ** 2
    return err / len(recs)

b3_te = brier(ite, tab3, lambda r: r['b3'], base_itr)
b6_te = brier(ite, tab6, lambda r: r['b6'], base_itr)
bconst_te = brier(ite, {}, lambda r: None, base_itr)
b3_tr = brier(itr, tab3, lambda r: r['b3'], base_itr)
b6_tr = brier(itr, tab6, lambda r: r['b6'], base_itr)
print('\nBrier（越低越好）:')
print('  常数基准      训练 %.5f  测试 %.5f' % (b3_tr and brier(itr, {}, lambda r: None, base_itr), bconst_te))
print('  3 档状态层    训练 %.5f  测试 %.5f' % (b3_tr, b3_te))
print('  6 档状态层    训练 %.5f  测试 %.5f' % (b6_tr, b6_te))
print('  6 档 vs 3 档: 训练 %+.5f | 测试 %+.5f  → %s' % (
    b6_tr - b3_tr, b6_te - b3_te,
    '✅测试段不差于 3 档（可上线）' if b6_te <= b3_te + 1e-9 else '❌测试段变差（不得上线）'))

# 6 档概率离散度（训练段收缩后）
import statistics as st2
p6 = sorted(tab6.values())
p3 = sorted(tab3.values())
print('\n概率取值离散度（训练段收缩后）: 3 档 %d 个值 (sd %.4f) | 6 档 %d 个值 (sd %.4f)' % (
    len(p3), st2.pstdev(p3), len(p6), st2.pstdev(p6)))

# -*- coding: utf-8 -*-
"""新因子诚实检验：训练段/测试段时间不重叠，逐因子分组上涨率同向性检验。
只有两段同向且幅度稳定的因子才允许纳入概率模型（v7.0 铁律）。"""
import json, os, sys
import statistics as st

ROOT = '/workspace/cailianshe-dashboard'
sys.path.insert(0, ROOT)
import quant as Q

klmap = json.load(open(os.path.join(ROOT, 'ref', 'kline320.json'), encoding='utf-8'))

def norm_with_dates(kline):
    """看板 kline [date, open, close, high, low, vol] → (date, open, high, low, close, vol)，保留日期。"""
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

# 指数 past10 查询（按日期对齐）
idx_past10 = {}
for i in range(10, len(idx_closes)):
    idx_past10[idx_d[i][0]] = idx_closes[i] / idx_closes[i - 10] - 1

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
        h = [b[1] for b in bars]
        l = [b[2] for b in bars]
        v = [b[4] for b in bars]
        date = bars_d[i][0]
        # 候选因子（全部为当日及以前信息）
        f = {}
        f['past10'] = c[i] / c[i - 10] - 1
        f['past5'] = c[i] / c[i - 5] - 1
        f['volRatio'] = ind['vol_ratio'][i]
        f['volPriceUp'] = (c[i] / c[i-1] - 1) * ind['vol_ratio'][i]  # 涨跌幅×量比
        f['relIdx'] = f['past10'] - idx_past10.get(date, 0.0)     # 相对大盘10日强弱
        f['emaAlign'] = (ind['e12'][i] / ind['e50'][i] - 1)       # EXPMA12 vs 50 排列
        f['devE50'] = c[i] / ind['e50'][i] - 1                     # 距 EXPMA50 偏离
        f['atrState'] = (ind['atrp'][i] / (st.mean([x for x in ind['atrp'][i-19:i+1] if x]) if any(ind['atrp'][i-19:i+1]) else ind['atrp'][i]))  # ATR 扩张/收缩
        f['consec'] = 0                                            # 连涨连跌天数（带符号）
        for k in range(1, min(8, i)):
            d0 = c[i-k+1] / c[i-k] - 1 if k >= 1 else 0
            if k == 1: f['consec'] = 1 if d0 > 0 else -1; continue
            if (d0 > 0) == (f['consec'] > 0): f['consec'] += 1 if d0 > 0 else -1
            else: break
        f['bollPos'] = ind['pb'][i]
        f['sdp'] = ind['sdp'][i]
        f['obvSlope'] = ind['obv_slope'][i]
        f['up'] = 1 if bars[i + H][3] > c[i] else 0
        f['date'] = date
        rows.append(f)

n = len(rows)
rows.sort(key=lambda r: r['date'])  # 按真实日期排序
# 严格按日期切分 70/30
dates = sorted(set(r['date'] for r in rows))
split_date = dates[int(len(dates) * 0.7)]
train = [r for r in rows if r['date'] < split_date]
test = [r for r in rows if r['date'] >= split_date]
print('观测总数 %d | 训练段 %d | 测试段 %d | 切分日 %s' % (n, len(train), len(test), split_date))

base_tr = sum(r['up'] for r in train) / len(train)
base_te = sum(r['up'] for r in test) / len(test)
print('训练段基准 %.1f%% | 测试段基准 %.1f%%\n' % (base_tr * 100, base_te * 100))

def check(key, bins, labels):
    def rates(rs):
        out = []
        for lo, hi in bins:
            seg = [r['up'] for r in rs if lo <= r[key] < hi]
            out.append((sum(seg) / len(seg) * 100, len(seg)) if len(seg) >= 25 else None)
        return out
    tr, te = rates(train), rates(test)
    trv = [x[0] if x else None for x in tr]
    tev = [x[0] if x else None for x in te]
    # 同向性：两段有效组间的单调方向一致（全部忽略 None）
    def mono(v):
        vv = [x for x in v if x is not None]
        if len(vv) < 3: return None
        diffs = [vv[i+1] - vv[i] for i in range(len(vv)-1)]
        return ('up' if all(d > 1.0 for d in diffs) else ('down' if all(d < -1.0 for d in diffs) else 'none'))
    mtr, mte = mono(trv), mono(tev)
    same = mtr in ('up', 'down') and mtr == mte  # 只有两段同为真实单调方向才算同向
    print('%-10s 训练: %s  测试: %s  单调方向: %s/%s  %s' % (
        key,
        ' '.join('%5.1f' % x if x else '  —  ' for x in trv),
        ' '.join('%5.1f' % x if x else '  —  ' for x in tev),
        mtr or '?', mte or '?',
        '✅同向' if same else ('❌' if mtr != mte else '')))
    return same, trv, tev

print('%-10s %-34s %-34s' % ('因子', '训练段分组上涨率%', '测试段分组上涨率%'))
print('-' * 90)
print('（labels: ' + ' / '.join(['Q1低→Q5高']*1) + '）')
check('past10',   [(-9,-0.06),(-0.06,-0.03),(-0.03,0.0),(0.0,0.06),(0.06,9)], None)
check('past5',    [(-9,-0.08),(-0.08,-0.03),(-0.03,0.0),(0.0,0.05),(0.05,9)], None)
check('volRatio', [(0,0.7),(0.7,1.0),(1.0,1.4),(1.4,2.0),(2.0,99)], None)
check('volPriceUp',[(-9,-0.01),(-0.01,0),(0,0.01),(0.01,0.03),(0.03,9)], None)
check('relIdx',   [(-9,-0.12),(-0.12,-0.05),(-0.05,0.02),(0.02,0.09),(0.09,9)], None)
check('emaAlign', [(-9,-0.03),(-0.03,-0.01),(-0.01,0.01),(0.01,0.03),(0.03,9)], None)
check('devE50',   [(-9,-0.10),(-0.10,-0.05),(-0.05,0.0),(0.0,0.06),(0.06,9)], None)
check('atrState', [(0,0.75),(0.75,0.9),(0.9,1.1),(1.1,1.3),(1.3,99)], None)
check('consec',   [(-9,-2.5),(-2.5,-0.5),(-0.5,0.5),(0.5,2.5),(2.5,9)], None)
check('bollPos',  [(0,0.1),(0.1,0.3),(0.3,0.6),(0.6,0.85),(0.85,1.01)], None)
check('sdp',      [(0,3.5),(3.5,4.5),(4.5,5.5),(5.5,7.0),(7.0,99)], None)
check('obvSlope', [(-99,-8),(-8,-2),(-2,2),(2,8),(8,99)], None)

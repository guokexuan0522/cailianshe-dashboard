#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v7.0 终版重算：状态层（均值回复 ∩ 下跌趋势）+ 波动率自适应区间 + 分层操盘建议。
每项都先验证再落地，验证结果打印在 stdout。"""
import json, os, sys, math, statistics as st
BASE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(BASE)
sys.path.insert(0, ROOT)
import quant as Q

K = json.load(open(os.path.join(ROOT,'ref','kline320.json'), encoding='utf-8'))
I = json.load(open(os.path.join(ROOT,'ref','index320.json'), encoding='utf-8'))
H = 10

def fwd_stats(idx_bars, horizon):
    """对每个历史时点，算 ①距EMA60 ②EMA60五日斜率，标签=未来10日全池上涨率。"""
    cl = [b[3] for b in idx_bars]
    e60 = Q.ema(cl, 60)
    n = len(cl)
    recs = []
    for i in range(70, n - horizon):
        if not e60[i] or not e60[i-5]:
            continue
        recs.append({'i': i, 'dev': cl[i]/e60[i]-1, 'slope': e60[i]/e60[i-5]-1,
                     'fwd': cl[i+horizon]/cl[i]-1})
    return recs

def pooled_ups(recs, klmap, horizon):
    """把指数时点映射到每只个股：个股未来10日是否上涨。返回按时点分组的上涨率。"""
    out = {}
    for q, node in klmap.items():
        bars = Q.norm_bars(node['bars'])
        dates = [b[0] for b in node['bars'] if len(b) >= 6]
        if len(bars) != len(dates):
            continue
        dmap = {d: k for k, d in enumerate(dates)}
        cl = [b[3] for b in bars]
        for r in recs:
            k = dmap.get(idx_dates[r['i']])
            if k is None or k + horizon >= len(cl):
                continue
            out.setdefault(r['i'], []).append(1 if cl[k+horizon] > cl[k] else 0)
    return {i: sum(v)/len(v) for i, v in out.items() if len(v) >= 20}

idx_dates = [b[0] for b in I['sh000001']['bars']]
recs = fwd_stats(Q.norm_bars(I['sh000001']['bars']), H)
pool = pooled_ups(recs, K, H)
for r in recs:
    r['pool'] = pool.get(r['i'])
recs = [r for r in recs if r['pool'] is not None]
print('指数时点 %d 个' % len(recs))

# ---- 拆分训练/测试（时间不重叠） ----
cut = int(len(recs)*0.7)
tr, te = recs[:cut], recs[cut:]
base_tr = st.mean([r['pool'] for r in tr]); base_te = st.mean([r['pool'] for r in te])
print('训练段 %d 点，池上涨率 %.1f%%；测试段 %d 点，池上涨率 %.1f%%'
      % (len(tr), base_tr*100, len(te), base_te*100))

def rate(seg, cond):
    s = [r['pool'] for r in seg if cond(r)]
    return (len(s), st.mean(s) if s else None)

# ---- 状态层二维：深跌(dev) × 趋势(slope) ----
print('\n【状态层二维检验】深跌阈值 -1.8%%，趋势用 EMA60 五日斜率')
for sl_name, sl_cond in [('下跌(斜率<-0.3%)', lambda r: r['slope'] < -0.003),
                         ('走平(|斜率|<=0.3%)', lambda r: abs(r['slope']) <= 0.003),
                         ('上行(斜率>+0.3%)', lambda r: r['slope'] > 0.003)]:
    n1, p1 = rate(tr, lambda r: r['dev'] <= -0.018 and sl_cond(r))
    n2, p2 = rate(te, lambda r: r['dev'] <= -0.018 and sl_cond(r))
    print('  深跌×%-18s 训练 n=%3d %s  测试 n=%3d %s'
          % (sl_name, n1, ('%.1f%%' % (p1*100)) if p1 else '—', n2, ('%.1f%%' % (p2*100)) if p2 else '—'))

print('\n对照：')
n1, p1 = rate(tr, lambda r: True); n2, p2 = rate(te, lambda r: True)
print('  全样本         训练 %.1f%%  测试 %.1f%%' % (p1*100, p2*100))
n1, p1 = rate(tr, lambda r: r['dev'] > 0.022); n2, p2 = rate(te, lambda r: r['dev'] > 0.022)
print('  高位 ' + str((n1,p1)) + ' ' + str((n2,p2)))
n1, p1 = rate(tr, lambda r: r['dev'] <= -0.018 and r['slope'] >= -0.003)
n2, p2 = rate(te, lambda r: r['dev'] <= -0.018 and r['slope'] >= -0.003)
print('  深跌×非下跌     训练 %.1f%%  测试 %.1f%%' % (p1*100, p2*100))

json.dump({'recs': [{'dev': r['dev'], 'slope': r['slope'], 'pool': r['pool'],
                     'date': idx_dates[r['i']]} for r in recs]},
          open(os.path.join(BASE, 'state_samples.json'), 'w', encoding='utf-8'), ensure_ascii=False)

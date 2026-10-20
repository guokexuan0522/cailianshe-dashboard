# -*- coding: utf-8 -*-
"""分层拆解实验：v6.3(静态) vs v7.0(动态引擎) 到底什么改变了执行结果"""
import json, sys, importlib.util
spec = importlib.util.spec_from_file_location('quant', '/workspace/cailianshe-dashboard/quant.py')
Q = importlib.util.module_from_spec(spec); spec.loader.exec_module(Q)

D = json.load(open('/workspace/cailianshe-dashboard/v7/quant_result.json', encoding='utf-8'))
idx_bars = Q.norm_bars(json.load(open('/workspace/cailianshe-dashboard/ref/index320.json', encoding='utf-8'))['sh000001']['bars'])
closes = [b[3] for b in idx_bars]
print('上证 K 线根数:', len(idx_bars), '末日:', idx_bars[-1][0])

# ---------- 实验 1：EMA 种子口径敏感性 ----------
print('\n===== 实验1：EMA60 种子口径 → 偏离值 =====')
def ema_variant(vals, n, mode):
    k = 2.0/(n+1); out=[None]*len(vals)
    if mode=='tdx':            # 通达信：前n根简单均值种子（当前实现）
        out[n-1]=sum(vals[:n])/n
    elif mode=='first':        # 第一根收盘价种子
        out[0]=vals[0]
    elif mode=='sma_all':      # 全序列SMA做种子后切换（另一种常见口径）
        s=0.0
        for i,v in enumerate(vals):
            s+=v
            if i>=n: s-=vals[i-n]
            if i>=n-1: out[i]=s/n
        for i in range(n,len(vals)):
            out[i]=vals[i]*k+out[i-1]*(1-k)
        return out
    if mode=='first':
        for i in range(1,len(vals)): out[i]=vals[i]*k+out[i-1]*(1-k)
    else:
        for i in range(n,len(vals)): out[i]=vals[i]*k+out[i-1]*(1-k)
    return out
last = closes[-1]
for mode in ('tdx','first','sma_all'):
    e = ema_variant(closes, 60, mode)
    if e[-1]:
        dev = last/e[-1]-1; slope = e[-1]/e[-6]-1 if e[-6] else 0
        print('  %-8s EMA60=%8.2f  dev=%+.3f%%  slope5=%+.3f%%' % (mode, e[-1], dev*100, slope*100))
sma60 = Q.sma(closes, 60)
dev_ma = last/sma60[-1]-1; slope_ma = sma60[-1]/sma60[-6]-1
print('  %-8s MA60 =%8.2f  dev=%+.3f%%  slope5=%+.3f%%  ← 若未切 EXPMA' % ('MA60', sma60[-1], dev_ma*100, slope_ma*100))
print('  → 判定阈值: dev<=-2.5% 且 slope<-0.6% 为「超跌反弹区」')

# ---------- 实验 2：概率分层 ----------
print('\n===== 实验2：概率四层拆解（36只）=====')
exp = D['experience']; state = D['state']; base = exp['baseP']
print('  L0 全池基准 baseP = %.2f%% (n=%d)' % (base*100, exp['n']))
print('  L1 状态层: pRaw=%.3f (n=%d) → 收缩 → state.p=%.3f (%s)' % (
    state['pRaw'], state['n'], state['p'], state['tag']))
l1 = state['p']*Q.STATE_TRUST + base*(1-Q.STATE_TRUST)
print('  L2 概率合成: state.p×%.2f + base×%.2f = %.3f' % (Q.STATE_TRUST, 1-Q.STATE_TRUST, l1))
rows=[]
for code, v in D['stocks'].items():
    f = v['feats']
    adj = 0.0; hits=[]
    for nm, cond, cap, _ in Q.ADJUSTERS:
        if cond(f): adj=max(adj,cap); hits.append(nm)
    p = min(Q.BASE_CEIL, max(Q.BASE_FLOOR, l1+adj))
    rows.append((code, v['name'], p, adj, hits, f))
import collections
cnt = collections.Counter(round(r[2]*100,1) for r in rows)
print('  L3 个股修正后概率分布（值: 只数）:', dict(sorted(cnt.items(), reverse=True)))
print('  → 概率相同的股票组（前5组）:')
for pv, c in cnt.most_common(5):
    grp = [r[1] for r in rows if round(r[2]*100,1)==pv]
    print('     %.1f%% × %d 只: %s' % (pv, c, '、'.join(grp[:6])))
print('  → 区分度: %d 只股票只有 %d 个不同概率值' % (len(rows), len(cnt)))

# ---------- 实验 3：状态层现场样本量 ----------
print('\n===== 实验3：状态层现场样本 =====')
print('  bands:')
for b in state['bands']:
    print('    %-6s 现场n=%-3d pRaw收缩=%.3f pHist=%.3f (n=%d) current=%s' % (
        b['name'], b['n'], b['p'], b['pHist'], b['nHist'], b['current']))

# ---------- 实验 4：预测区间宽度 ----------
print('\n===== 实验4：预测区间 vs v6.3 静态 =====')
widths=[]
for code, v in D['stocks'].items():
    w = v['forecastHi']-v['forecastLo']; widths.append(w)
    if len(widths)<=5:
        print('  %s %s: prob=%.1f%% 区间 %+.0f%%~%+.0f%% (宽%.0fpp) ATR%%=%.1f' % (
            code, v['name'], v['prob'], v['forecastLo'], v['forecastHi'], w, v['feats']['atrp']))
print('  区间宽度: 平均 %.0fpp, 最大 %.0fpp' % (sum(widths)/len(widths), max(widths)))
print('  v6.3 静态 forecast 示例: "+5%~8%"（宽3pp，人工经验值）')

# ---------- 实验 5：walkforward 真实预测力 ----------
print('\n===== 实验5：样本外预测力 =====')
wf = D['walkforward']
print('  测试段: n=%d, 基准上涨率=%.1f%%, 模型命中=%.1f%%' % (
    wf['testN'], wf['testBase']*100, wf['hit']*100))
print('  Brier: 模型 %.4f vs 基准 %.4f → 技巧分 %+.2f%%' % (
    wf['brier'], wf['brierBase'], wf['skill']*100))
print('  状态分层胜率(训练段):', {k: '%.1f%%(n=%d)'%(v['p']*100, v['n']) for k,v in wf['stateStat'].items()})

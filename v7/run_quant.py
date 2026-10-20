#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v7.0 步骤 D：完整跑量化引擎 —— 经验概率查表 + 状态融合 + 样本外验证。"""
import json, os, sys, time, statistics as st

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
sys.path.insert(0, ROOT)
import quant as Q

klmap = json.load(open(os.path.join(ROOT, 'ref', 'kline320.json'), encoding='utf-8'))
idx = json.load(open(os.path.join(ROOT, 'ref', 'index320.json'), encoding='utf-8'))
idxbars = Q.norm_bars(idx['sh000001']['bars'])

print('=' * 80)
print('① 市场状态层（上证指数 %d 根日K）' % len(idxbars))
print('=' * 80)
state = Q.index_state(idxbars, 10)
print('当前距EXPMA60 %+.2f%% → 状态：%s' % (state['mid'] * 100, state['tag']))
print('该档历史：n=%d，10日上涨 %s（收缩后 %.1f%%）'
      % (state['n'], ('%.1f%%' % (state['pRaw'] * 100)) if state['pRaw'] is not None else '—', state['p'] * 100))
print('全样本基准：%.1f%%（n=%d）' % (state['baseP'] * 100, state['baseN']))
print('\n各档：')
for b in state['bands']:
    print('  %-8s n=%3d  10日上涨 %s' % (b['name'], b['n'],
          ('%.1f%%' % (b['p'] * 100)) if b['p'] is not None else '—'))

print()
print('=' * 80)
print('② 经验概率查表（全池历史样本 → 条件上涨频率）')
print('=' * 80)
exp, samples = Q.build_experience(klmap, None, horizon=10)
print('基准上涨率（10日）= %.2f%%   样本 n=%d   覆盖 %d 只股票'
      % (exp['baseP'] * 100, exp['n'], exp['stocks']))
print('\n修正项（仅保留样本外验证成立的信号）：')
for name, cond, cap, note in Q.ADJUSTERS:
    if name == 'deep':
        print('  %-8s +%.1f~+%.1fpp（按偏离深度连续）   %s'
              % (name, cap({'devE12': -0.03, 'rsi': 0.0, 'pos': 0.0}) * 100,
                 cap({'devE12': -0.10, 'rsi': 0.0, 'pos': 0.0}) * 100, note))
    else:
        print('  %-8s +%.1fpp   %s' % (name, cap({'devE12': 0.0, 'rsi': 0.0, 'pos': 0.0}) * 100, note))
print('  状态项    ×%.2f     指数深度超跌时按历史幅度加权（样本外验证成立）' % Q.STATE_TRUST)
print('  限幅      [%.0f%%, %.0f%%]' % (Q.BASE_FLOOR * 100, Q.BASE_CEIL * 100))

print()
print('=' * 80)
print('③ 逐只分析')
print('=' * 80)
res = Q.analyze_all(klmap, exp, samples, state, 10)
print('%-9s %6s %6s %7s %7s %7s %5s  %-4s %-10s %s'
      % ('名称', '概率', '基准', '偏离', '10日涨幅', 'RSI', 'ATR%', '置信', '建议', '区间'))
probs, confs, advs = [], {}, {}
for q in sorted(res, key=lambda x: -res[x]['prob']):
    r = res[q]
    probs.append(r['prob'])
    confs[r['conf']] = confs.get(r['conf'], 0) + 1
    advs[r['advice']['action']] = advs.get(r['advice']['action'], 0) + 1
    print('%-9s %5.1f%% %5.1f%% %+6.1f %+7.1f%% %7.1f %5.1f  %-4s %-10s %s'
          % (r['name'], r['prob'], r['probBase'], r['prob'] - r['probBase'],
             r['feats']['past10'] * 100, r['feats']['rsi'], r['feats']['atrp'],
             r['conf'], r['advice']['action'], r['forecast']))
print('\n概率 min %.1f  max %.1f  mean %.1f  sd %.2f'
      % (min(probs), max(probs), st.mean(probs), st.pstdev(probs)))
print('置信度：', confs)
print('建议：', advs)

print()
print('=' * 80)
print('④ 样本外滚动验证（真 walk-forward）')
print('=' * 80)
t0 = time.time()
idx_dates = [b[0] for b in idx['sh000001']['bars']]
wf = Q.validate(klmap, idxbars, 10, step=1, idx_raw=idx_dates)
print('用时 %.1fs' % (time.time() - t0))
if wf:
    print('预测点 n=%d' % wf['n'])
    print('训练段 %d 个观测（基准上涨率 %.1f%%），测试段 %d 个观测（基准上涨率 %.1f%%）'
          % (wf['trainN'], wf['trainBase'] * 100, wf['testN'], wf['testBase'] * 100))
    print('方向命中率 %.1f%%' % (wf['hit'] * 100))
    print('Brier %.4f vs 基准 %.4f → 技巧分 %+.2f%%' % (wf['brier'], wf['brierBase'], wf['skill'] * 100))
    print('概率 vs 实际上涨 相关系数 %+.4f' % wf['corr'])
    lb, hb = wf['lowBucket'], wf['highBucket']
    print('低概率组：预测 %.1f%% / 实际 %.1f%% / 平均收益 %+.2f%%（n=%d）'
          % (lb['pred'] * 100, lb['actual'] * 100, lb['avgRet'] * 100, lb['n']))
    print('高概率组：预测 %.1f%% / 实际 %.1f%% / 平均收益 %+.2f%%（n=%d）'
          % (hb['pred'] * 100, hb['actual'] * 100, hb['avgRet'] * 100, hb['n']))
    print('高低组实际上涨率差 %+.1f 个百分点' % (wf['spread'] * 100))
    # 校准：预测值 vs 实际值 的偏差
    print('校准偏差（预测-实际）：低组 %+.1f pp，高组 %+.1f pp'
          % ((lb['pred'] - lb['actual']) * 100, (hb['pred'] - hb['actual']) * 100))

print()
print('=' * 80)
print('⑤ EXPMA vs MA 实测（分位穿越领先性）')
print('=' * 80)
lu, ld, al = [], [], []
for q, node in klmap.items():
    r = Q.ema_lead(Q.norm_bars(node['bars']), 12, 1.0)
    if r:
        lu.append(r['leadUp']); ld.append(r['leadDn']); al.append(r['lead'])
print('样本 %d 只；EXPMA12 相对 MA12：' % len(al))
print('  上穿信号平均提前 %.2f 个交易日' % st.mean(lu))
print('  下穿信号平均提前 %.2f 个交易日' % st.mean(ld))
print('  综合平均提前 %.2f 个交易日（中位数 %.2f）' % (st.mean(al), st.median(al)))

json.dump({'state': state, 'experience': exp, 'stocks': res, 'walkforward': wf},
          open(os.path.join(ROOT, 'v7', 'quant_result.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('\n→ v7/quant_result.json')

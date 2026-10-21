# -*- coding: utf-8 -*-
"""v8.2 stage3：重建 review 今日收盘数据复盘（量化建议 + 技术面要点 + 止损/支撑/压力）"""
import json, os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import quant

d = json.load(open('/tmp/stage2.json', encoding='utf-8'))
HORIZON = 10

# ---- 市场状态层（上证指数日K，与页面 QX_STATE 同源）----
idx_bars = quant.norm_bars(d['quant']['index']['bars'])
STATE = quant.index_state(idx_bars, HORIZON)
BASE = (STATE or {}).get('baseP', 0.4955)
print('市场状态:', (STATE or {}).get('tag'), 'baseP=%.4f' % BASE)

# ---- 经验层：build_experience 需要全池日K ----
klmap = {}
for w in d['watchlist']:
    st = d['stocks'].get(w['q']) or {}
    if st.get('kline'):
        klmap[w['q']] = {'bars': st['kline'], 'name': w['name']}
print('日K可用:', len(klmap), '/', len(d['watchlist']))

exp, _ = quant.build_experience(klmap, None, HORIZON)
print('baseP(exp)=%.4f' % exp.get('baseP', 0))

res = quant.analyze_all(klmap, exp, None, STATE, HORIZON)


def ma(vals, n):
    if len(vals) < n:
        return None
    return sum(vals[-n:]) / n


def tech_point(w, st, r):
    """技术面要点：全部由内嵌日K与实时行情计算，不引入外部主观判断。"""
    k = st.get('kline') or []
    if len(k) < 21:
        return '日K数据不足（<21根），暂无技术面要点。'
    c = k[-1][2]
    cl = [x[2] for x in k]
    m5, m20 = ma(cl, 5), ma(cl, 20)
    rsi = r['rsi'] if r else 50
    atrp = r['atrp'] if r else 3.0
    p5 = (c / k[-6][2] - 1) * 100
    p20 = (c / k[-21][2] - 1) * 100
    pos20 = r['feats']['pos'] if r else 0.5
    parts = []
    parts.append('现价 %.2f（今日 %s）' % (c, ('%+.2f%%' % (st.get('pct') or 0))))
    parts.append('5日 %+.1f%% · 20日 %+.1f%%' % (p5, p20))
    parts.append('MA5/MA20 %s' % ('多头排列' if m5 > m20 else '空头排列'))
    parts.append('RSI14 %.0f%s' % (rsi, '（超买）' if rsi > 80 else ('（超卖）' if rsi < 25 else '')))
    parts.append('20日区间位置 %.0f%%' % (pos20 * 100))
    parts.append('ATR%% %.1f（波动%s）' % (atrp, '偏高' if atrp >= 6 else '正常'))
    return ' · '.join(parts)


def build_advice(w, st, r):
    if not r:
        return None
    a = dict(r['advice'])
    k = st.get('kline') or []
    lo20 = min(x[3] for x in k[-20:]) if len(k) >= 20 else None
    hi20 = max(x[2] for x in k[-20:]) if len(k) >= 20 else None
    if lo20 is not None:
        a['sup'] = round(lo20, 2)
    if hi20 is not None:
        a['res'] = round(hi20, 2)
    a['tags'] = ['量化概率 %.1f%%' % r['prob'],
                 '市场状态 ' + ((STATE or {}).get('tag') or '—'),
                 'EXPMA12 %s' % ('上方' if (r['ema']['e12'] or 0) <= (st.get('price') or 0) else '下方')]
    gs = w.get('gainSince')
    pi = w.get('priceIn')
    stop_line = round(pi * 0.92, 2) if pi else None
    pct = st.get('pct') or 0
    hard = []
    if gs is not None and stop_line is not None:
        if gs <= -8:
            a['stop'] = stop_line
            hard.append('R3:入选以来%.1f%%，已跌破-8%%止损线%.2f' % (gs, stop_line))
        elif gs <= -6.5:
            a['nearStop'] = stop_line
            hard.append('R3预警:入选以来%.1f%%，已逼近-8%%止损线%.2f' % (gs, stop_line))
    if (r['rsi'] or 0) > 80:
        hard.append('R2:RSI%.0f>80 超买，勿追高' % r['rsi'])
    if pct >= 9.8:
        hard.append('R4:今日涨停（%+.2f%%），情绪高点，注意次日冲高回落' % pct)
    elif pct <= -9.8:
        hard.append('R4:今日跌停（%+.2f%%），注意流动性风险' % pct)
    if r['feats'].get('past5', 0) < -0.15:
        hard.append('R1:近5日累计%.1f%%，急跌未止' % (r['feats']['past5'] * 100))
    if hard:
        a['hard'] = hard
    return a


review_stocks = []
for w in d['watchlist']:
    st = d['stocks'].get(w['q']) or {}
    r = res.get(w['q'])
    review_stocks.append({
        'name': w['name'], 'code': w['code'], 'q': w['q'], 'sector': w.get('sector') or '',
        'priceIn': w.get('priceIn'), 'price': st.get('price') or w.get('priceNow'),
        'pct': st.get('pct') or 0, 'gainSince': w.get('gainSince'),
        'column': w.get('column'), 'aid': w.get('aid'), 'bulletNo': w.get('bulletNo'),
        'point': tech_point(w, st, r),
        'advice': build_advice(w, st, r),
    })

# 复盘日期 = 行情日期
qt = None
for st in d['stocks'].values():
    t = str(st.get('time') or '')
    if len(t) >= 8 and t[:8].isdigit():
        qt = '%s-%s-%s' % (t[:4], t[4:6], t[6:8])
        break
d['review'] = {'date': qt or '2026-10-21', 'stocks': review_stocks,
               'note': '复盘展示全部在池标的（勾选自选后在表内筛选展示）；技术面要点由内嵌日K实时计算，操盘建议由量化模型生成，参数页内公开可复算。'}

json.dump(d, open('/tmp/stage3.json', 'w', encoding='utf-8'), ensure_ascii=False)
print('stage3 ok: review.date=%s stocks=%d' % (d['review']['date'], len(review_stocks)))
for x in review_stocks[:3]:
    print(' ', x['name'], x['advice']['action'] if x['advice'] else None, '|', x['point'][:90])

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calc_signals.py — 复盘表【操盘建议】量化引擎（v4.28 模型规范的唯一实现）

输入：单只股票 80 根日K（[date, open, close, high, low, volume]，前复权）
      + 当日收盘行情（price/prev/pct/vol）
      + 入选价 priceIn（用于 R3 止损线）
计算：MA5/MA10/MA20、MACD(12,26,9)、RSI(14,Wilder)、KDJ(9,3,3)、
      BOLL(20,2) 及 %B、乖离 BIAS20、量比（当日量/前5日均量）、ATR14、近20日高低点
评分：七维加权（趋势2.0/MACD2.0/RSI1.0/KDJ1.0/BOLL1.0/BIAS1.0/量价1.0），总分[-10,+10]
指令：≥+3.5 买进(30%~60%) / +1.5~+3.5 逢低增持(20%~30%) / -1.5~+1.5 持有观望 /
      -3.5~-1.5 减仓(卖50%) / ≤-3.5 卖出(≥80%或清仓)
风控：R1 破位（跌破20日低点且MACD绿柱）强制卖出
      R2 RSI>80 禁止买进（降为持有观望）
      R3 入选以来≤-8% 触发止损线(priceIn*0.92)；-5%~-8% 预警
      R4 涨跌停日（pct≥9.8% 或 ≤-9.8%，20cm 板按 19.9%）指令降半级
输出：advice dict（action/pos/score/tags/sup/res/stop/nearStop/hard）

用法：
    from calc_signals import calc
    advice = calc(kline, quote, price_in)
    # 或命令行：python3 calc_signals.py kline.json quote.json price_in
"""
import json
import sys

# ---------------------------------------------------------------- 基础指标

def _ma(closes, n):
    if len(closes) < n:
        return None
    return sum(closes[-n:]) / n


def _ema_series(values, n):
    """指数移动平均序列（与同花顺/通达信一致的递归 EMA）"""
    k = 2.0 / (n + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def _macd(closes):
    """返回 (dif, dea, hist) 序列；hist 为 MACD 柱（红正绿负）"""
    ema12 = _ema_series(closes, 12)
    ema26 = _ema_series(closes, 26)
    dif = [a - b for a, b in zip(ema12, ema26)]
    dea = _ema_series(dif, 9)
    hist = [(d - e) * 2 for d, e in zip(dif, dea)]
    return dif, dea, hist


def _rsi_wilder(closes, n=14):
    """Wilder 平滑 RSI 序列"""
    if len(closes) < n + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    ag = sum(gains[:n]) / n
    al = sum(losses[:n]) / n
    for i in range(n, len(gains)):
        ag = (ag * (n - 1) + gains[i]) / n
        al = (al * (n - 1) + losses[i]) / n
    if al == 0:
        return 100.0 if ag > 0 else 50.0
    rs = ag / al
    return 100.0 - 100.0 / (1.0 + rs)


def _kdj(klines, n=9, m1=3, m2=3):
    """返回 (K, D, J) 序列"""
    if len(klines) < n:
        return None, None, None
    ks, ds, js = [], [], []
    k_prev = d_prev = 50.0
    for i in range(len(klines)):
        lo = min(x[4] for x in klines[max(0, i - n + 1):i + 1])
        hi = max(x[3] for x in klines[max(0, i - n + 1):i + 1])
        rsv = 50.0 if hi == lo else (klines[i][2] - lo) / (hi - lo) * 100.0
        k_prev = (m1 - 1) / m1 * k_prev + rsv / m1
        d_prev = (m2 - 1) / m2 * d_prev + k_prev / m2
        j = 3 * k_prev - 2 * d_prev
        ks.append(k_prev)
        ds.append(d_prev)
        js.append(j)
    return ks, ds, js


def _boll(closes, n=20, k=2.0):
    """返回 (mid, upper, lower, pctB) 序列"""
    if len(closes) < n:
        return None, None, None, None
    mids, ups, lows, pbs = [], [], [], []
    for i in range(n - 1, len(closes)):
        window = closes[i - n + 1:i + 1]
        mid = sum(window) / n
        var = sum((x - mid) ** 2 for x in window) / n
        sd = var ** 0.5
        up, lo = mid + k * sd, mid - k * sd
        pb = (closes[i] - lo) / (up - lo) if up != lo else 0.5
        mids.append(mid)
        ups.append(up)
        lows.append(lo)
        pbs.append(pb)
    return mids, ups, lows, pbs


def _atr(klines, n=14):
    """kline 行格式: [date, open, close, high, low, volume]"""
    if len(klines) < n + 1:
        return None
    trs = []
    for i in range(1, len(klines)):
        h, l, pc = klines[i][3], klines[i][4], klines[i - 1][2]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr = sum(trs[:n]) / n
    for i in range(n, len(trs)):
        atr = (atr * (n - 1) + trs[i]) / n
    return atr


# ---------------------------------------------------------------- 主计算

def calc(kline, quote, price_in):
    """kline: [[date,o,c,h,l,v],...]（至少60根，取最后80根）
    quote: {price, prev, pct, vol, ...}
    price_in: 入选价（None 表示无法计算 R3）
    返回 advice dict"""
    kline = kline[-80:]
    closes = [x[2] for x in kline]   # index2=收盘价（v4.33 修正：此前误取 index1 开盘价，致 MA/MACD/RSI/BOLL/BIAS 全部基于开盘价计算）
    price = float(quote['price'])
    prev = float(quote['prev'])
    pct = float(quote.get('pct', (price - prev) / prev * 100 if prev else 0.0))
    vol_today = float(quote.get('vol') or kline[-1][5])

    ma5, ma10, ma20 = _ma(closes, 5), _ma(closes, 10), _ma(closes, 20)
    dif, dea, hist = _macd(closes)
    rsi = _rsi_wilder(closes)
    ks, ds, js = _kdj(kline)
    mids, ups, lows, pbs = _boll(closes)
    atr = _atr(kline)
    hi20 = max(x[3] for x in kline[-20:])
    lo20 = min(x[4] for x in kline[-20:])

    # 量比：当日量 / 前5日均量
    vols5 = [x[5] for x in kline[-6:-1]]
    vol_ratio = vol_today / (sum(vols5) / len(vols5)) if vols5 and sum(vols5) > 0 else 1.0
    bias20 = (price - ma20) / ma20 * 100 if ma20 else 0.0

    d_dif, d_dea, d_hist = dif[-1], dea[-1], hist[-1]
    k, d = ks[-1], ds[-1]
    mid, up, lo, pb = mids[-1], ups[-1], lows[-1], pbs[-1]

    tags = []
    score = 0.0

    # ---- 维度1 趋势（2.0）
    if ma5 and ma10 and ma20:
        if price > ma5 > ma10 > ma20:
            score += 2.0
            tags.append('多头排列(价>MA5>MA10>MA20)')
        elif price < ma5 < ma10 < ma20 and price < ma20:
            score -= 2.0
            tags.append('空头排列(MA5<MA10<MA20)且价在MA20下方')
        elif price > ma20 and ma5 > ma10:
            score += 1.5
            tags.append('价在MA20上方且短期均线多头')
        elif price < ma20 and ma5 < ma10:
            score -= 1.5
            tags.append('价在MA20下方且短期均线空头')
        elif price > ma20:
            score += 1.0
            tags.append('价在MA20上方')
        else:
            score -= 1.0
            tags.append('价在MA20下方')

    # ---- 维度2 MACD（2.0）
    if d_dif > 0 and d_dea > 0:
        if d_hist > 0:
            score += 2.0
            tags.append('零轴上方红柱(DIF/DEA双正)')
        else:
            score += 1.0
            tags.append('零轴上方红柱收敛(DIF/DEA双正)')
    elif d_dif < 0 and d_dea < 0:
        if d_hist < 0:
            score -= 2.0
            tags.append('零轴下方绿柱放大(DIF/DEA双负)')
        else:
            score -= 1.0
            tags.append('零轴下方绿柱收敛(DIF/DEA双负)')
    elif d_dif > d_dea:
        score += 0.5
        tags.append('DIF上穿DEA金叉')
    else:
        score -= 0.5
        tags.append('DIF下穿DEA死叉')

    # ---- 维度3 RSI（1.0）
    if rsi is not None:
        if rsi > 80:
            score -= 1.0
            tags.append('RSI%.0f>80超买' % rsi)
        elif rsi < 20:
            score += 1.0
            tags.append('RSI%.0f<20超卖' % rsi)
        elif rsi < 50:
            score += 0.5
            tags.append('RSI%.0f弱势区' % rsi)
        elif rsi > 65:
            score -= 0.5
            tags.append('RSI%.0f强势区上方' % rsi)
        else:
            tags.append('RSI%.0f中性区' % rsi)

    # ---- 维度4 KDJ（1.0）
    if k is not None:
        if k > d:
            if k < 20:
                score += 1.0
                tags.append('低位金叉(K%.0f>D%.0f)' % (k, d))
            else:
                score += 0.5
                tags.append('KDJ金叉状态(K%.0f>D%.0f)' % (k, d))
        else:
            if k > 80:
                score -= 1.0
                tags.append('高位死叉(K%.0f<D%.0f)' % (k, d))
            else:
                score -= 0.5
                tags.append('KDJ死叉状态(K%.0f<D%.0f)' % (k, d))

    # ---- 维度5 BOLL 位置（1.0）
    if pb is not None:
        if pb < 0:
            score += 0.5
            tags.append('触布林下轨(%%B=%.2f),均值回归' % pb)
        elif pb > 1:
            score -= 0.5
            tags.append('触布林上轨(%%B=%.2f),均值回归' % pb)
        elif pb < 0.2:
            score += 0.25
            tags.append('贴近布林下轨(%%B=%.2f)' % pb)
        elif pb > 0.8:
            score -= 0.25
            tags.append('贴近布林上轨(%%B=%.2f)' % pb)

    # ---- 维度6 BIAS20（1.0）
    if bias20 > 10:
        score -= 1.0
        tags.append('BIAS20=%.1f%%正乖离过大' % bias20)
    elif bias20 < -10:
        score += 1.0
        tags.append('BIAS20=%.1f%%负乖离过大' % bias20)
    elif bias20 > 6:
        score -= 0.5
        tags.append('BIAS20=%.1f%%偏高' % bias20)
    elif bias20 < -6:
        score += 0.5
        tags.append('BIAS20=%.1f%%偏低' % bias20)

    # ---- 维度7 量价（1.0）
    if pct > 0 and vol_ratio > 1.5:
        score += 1.0
        tags.append('放量上涨(量比%.2f)' % vol_ratio)
    elif pct > 0:
        score += 0.5
        tags.append('上涨(量比%.2f)' % vol_ratio)
    elif pct < 0 and vol_ratio > 1.5:
        score -= 1.0
        tags.append('放量下跌(量比%.2f)' % vol_ratio)
    elif pct < 0:
        score -= 0.5
        tags.append('下跌(量比%.2f)' % vol_ratio)

    score = round(max(-10.0, min(10.0, score)), 1)

    # ---- 指令映射
    if score >= 3.5:
        action, pos = '买进', '30%~60%'
    elif score >= 1.5:
        action, pos = '逢低增持', '20%~30%'
    elif score > -1.5:
        action, pos = '持有观望', '维持现有仓位'
    elif score > -3.5:
        action, pos = '减仓', '卖50%'
    else:
        action, pos = '卖出', '≥80%或清仓'

    hard = []

    # ---- R1 破位强制卖出（score 同步置满分负，与「强制卖出」语义一致）
    r1_break = price < lo20 and d_hist < 0
    if r1_break:
        action, pos = '卖出', '≥80%或清仓'
        score = -10.0
        hard.append('R1破位:跌破20日低点%.2f且MACD绿柱,强制卖出' % lo20)

    # ---- R2 RSI>80 禁止买进
    if rsi is not None and rsi > 80 and action in ('买进', '逢低增持'):
        action, pos = '持有观望', '维持现有仓位'
        hard.append('R2超买:RSI%.0f>80,禁止买进' % rsi)

    # ---- R3 止损线/预警（基于入选以来涨跌幅）
    if price_in:
        gain = (price - price_in) / price_in * 100
        if gain <= -8:
            action, pos = '卖出', '≥80%或清仓'
            hard.append('R3止损:入选以来%.1f%%,触发-8%%止损线%.2f' % (gain, price_in * 0.92))
        elif gain <= -5:
            hard.append('R3预警:入选以来%.1f%%,已逼近-8%%止损线%.2f' % (gain, price_in * 0.92))

    # ---- R4 涨跌停日降半级
    limit_up = pct >= 19.8
    limit_down = pct <= -19.8
    big_up = pct >= 9.8
    big_down = pct <= -9.8
    if limit_up or limit_down or big_up or big_down:
        rank = {'买进': 4, '逢低增持': 3, '持有观望': 2, '减仓': 1, '卖出': 0}
        inv = {v: k for k, v in rank.items()}
        r = rank[action]
        # 涨停日降温一档、跌停日降温一档（降半级：仅对买进行向降档，卖出行向不变）
        if action in ('买进', '逢低增持'):
            r = max(2, r - 1)
        action = inv[r]
        pos = {'买进': '30%~60%', '逢低增持': '20%~30%', '持有观望': '维持现有仓位',
               '减仓': '卖50%', '卖出': '≥80%或清仓'}[action]
        hard.append('R4涨跌停日指令降半级(当日%.2f%%)' % pct)

    stop = price_in * 0.92 if (price_in and (price - price_in) / price_in * 100 <= -8) else None
    near_stop = price_in * 0.92 if (price_in and -8 < (price - price_in) / price_in * 100 <= -5) else None

    return {
        'action': action,
        'pos': pos,
        'score': score,
        'tags': tags,
        'sup': round(lo20, 2),
        'res': round(hi20, 2),
        'stop': round(stop, 2) if stop else None,
        'nearStop': round(near_stop, 2) if near_stop else None,
        'hard': hard,
    }


if __name__ == '__main__':
    # 命令行自测：python3 calc_signals.py <kline.json> <quote.json> <price_in>
    kline = json.load(open(sys.argv[1]))
    quote = json.load(open(sys.argv[2]))
    price_in = float(sys.argv[3]) if len(sys.argv) > 3 else None
    print(json.dumps(calc(kline, quote, price_in), ensure_ascii=False, indent=1))

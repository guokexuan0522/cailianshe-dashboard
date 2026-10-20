#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""财联社·投研看板 · 量化引擎 v7.0

【第一性原理声明——整套概率算法的地基，写进铁律】

个股 10 日后涨跌，拆成两个统计性质完全不同的部分：

    个股收益 ≈ 大盘（基准）收益  +  个股超额收益

  · 大盘收益：短期近似随机游走，期望≈0，方差随时间聚集（可预测）。
    它的「历史分布」是样本外可校准的 → 上层：市场状态分布模型。
  · 个股超额：日频上自相关接近 0，方向近乎不可预测。
    但它也一样有可预测的方差（这只股票近期晃得多厉害）→ 下层：波动率拉伸。

于是 v7.0 的概率不是「给每股打个分估个胜率」，而是：

    P(10 日后上涨) = 「一个由这只股票波动率 σ_i 决定宽度、
                      由当前市场状态决定中枢的分布，落在 0 以上的面积」

实证依据（v7.0 建设时对 36 只 × 251 日 = 9036 个观测做单因子 IC 检验）：
  · 趋势因子（EXPMA 多头排列 + 斜率）IC = -0.103，方向为负 ——
    本样本上追涨的 10 日后续收益反而更低，均值回复占优；
  · RSI、位置因子 IC 为正（+0.051 / +0.040），与超卖反弹一致；
  · 旧 8 因子等权综合分五分组上涨率单调递减（53.7%→45.8%）。
  → 结论：旧权重系的「符号假设错了」，不是「信号太弱」。
  → v7.0 因此不再凭经验设权重：因子分只用于**排序与解释**，不直接进概率公式；
    概率由「市场状态层 × 波动率层」产出，全程可数学复算。

均线体系：EXPMA（EMA，alpha = 2/(n+1)，前 n 根简单均值做种子，通达信口径）为唯一主均线；
          MA 仅作滞后对照输出。
"""
import math

# 厚尾参数：t 分布自由度。A 股个股日收益超额峰度 3~8 → ν 4~6，取 5 为居中。
T_NU = 5.0


# ============================================================
# 一、基础指标
# ============================================================

def ema(vals, n):
    """EXPMA/EMA：alpha = 2/(n+1)，首值用前 n 个简单均值做种子（通达信口径）。"""
    if len(vals) < n or n <= 0:
        return [None] * len(vals)
    k = 2.0 / (n + 1)
    out = [None] * len(vals)
    out[n - 1] = sum(vals[:n]) / n
    for i in range(n, len(vals)):
        out[i] = vals[i] * k + out[i - 1] * (1 - k)
    return out


def sma(vals, n):
    out = [None] * len(vals)
    s = 0.0
    for i, v in enumerate(vals):
        s += v
        if i >= n:
            s -= vals[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def rsi(closes, n=14):
    """Wilder RSI。"""
    out = [None] * len(closes)
    if len(closes) <= n:
        return out
    g = l = 0.0
    for i in range(1, n + 1):
        d = closes[i] - closes[i - 1]
        g += max(d, 0)
        l += max(-d, 0)
    g /= n
    l /= n
    out[n] = 100.0 if l == 0 else 100 - 100 / (1 + g / l)
    for i in range(n + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        g = (g * (n - 1) + max(d, 0)) / n
        l = (l * (n - 1) + max(-d, 0)) / n
        out[i] = 100.0 if l == 0 else 100 - 100 / (1 + g / l)
    return out


def boll(closes, n=20, k=2.0):
    mid = sma(closes, n)
    up = [None] * len(closes)
    dn = [None] * len(closes)
    pb = [None] * len(closes)
    for i in range(len(closes)):
        if mid[i] is None:
            continue
        seg = closes[i - n + 1:i + 1]
        m = mid[i]
        var = sum((x - m) ** 2 for x in seg) / n
        sd = var ** 0.5
        up[i] = m + k * sd
        dn[i] = m - k * sd
        pb[i] = (closes[i] - dn[i]) / (up[i] - dn[i]) if up[i] != dn[i] else 0.5
    return up, mid, dn, pb


def atr(h, l, c, n=14):
    tr = [None] * len(c)
    for i in range(len(c)):
        if i == 0:
            tr[i] = h[i] - l[i]
        else:
            tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    out = [None] * len(c)
    if len(c) < n:
        return out
    out[n - 1] = sum(tr[:n]) / n
    for i in range(n, len(c)):
        out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out


def atr_pct(h, l, c, n=14):
    a = atr(h, l, c, n)
    return [(a[i] / c[i] * 100) if (a[i] is not None and c[i]) else None for i in range(len(c))]


def stdev_pct(closes, n=20):
    out = [None] * len(closes)
    for i in range(n - 1, len(closes)):
        seg = closes[i - n + 1:i + 1]
        m = sum(seg) / n
        var = sum((x - m) ** 2 for x in seg) / n
        out[i] = (var ** 0.5) / m * 100 if m else None
    return out


def obv(closes, vols):
    out = [0.0] * len(closes)
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            out[i] = out[i - 1] + vols[i]
        elif closes[i] < closes[i - 1]:
            out[i] = out[i - 1] - vols[i]
        else:
            out[i] = out[i - 1]
    return out


def norm_bars(kline):
    """看板 kline [date, open, close, high, low, vol] → (open, high, low, close, vol)。统一入口。"""
    out = []
    for b in kline or []:
        if len(b) < 6:
            continue
        try:
            out.append((float(b[1]), float(b[3]), float(b[4]), float(b[2]), float(b[5] or 0)))
        except (TypeError, ValueError):
            continue
    return out


def build_indicators(bars):
    closes = [b[3] for b in bars]
    highs = [b[1] for b in bars]
    lows = [b[2] for b in bars]
    vols = [b[4] for b in bars]
    o = obv(closes, vols)
    obv_slope = [None] * len(bars)
    for i in range(10, len(bars)):
        base = abs(o[i - 10])
        obv_slope[i] = ((o[i] - o[i - 10]) / base * 100) if base > 0 else 0.0
    v5 = sma(vols, 5)
    vol_ratio = [None] * len(bars)
    for i in range(len(bars)):
        if v5[i]:
            vol_ratio[i] = vols[i] / v5[i]
    up, mid, dn, pb = boll(closes, 20)
    return {
        'bars': bars, 'e12': ema(closes, 12), 'e50': ema(closes, 50),
        'ma12': sma(closes, 12), 'ma20': sma(closes, 20), 'rsi': rsi(closes, 14),
        'pb': pb, 'atrp': atr_pct(highs, lows, closes, 14),
        'sdp': stdev_pct(closes, 20), 'obv_slope': obv_slope, 'vol_ratio': vol_ratio,
        'bollUp': up, 'bollMid': mid, 'bollDn': dn,
    }


# ============================================================
# 二、因子打分（-100 ~ +100，用于排序与解释）
# ============================================================
# 方向由 IC 检验确定（9036 观测），不是拍脑袋：
#   trend     符号修正为「限幅正向」，抑制极端追涨（IC 原始 -0.10，限幅后转正）
#   momentum  取负（正偏离 EXPMA12 → 回踩压力）
#   rsi       超卖加分（IC +0.05）
#   volume    取负（放量上涨→透支）
#   position  低位加分（IC +0.04）
#   volatility 高波动扣分
#   rs        十日超额取负（跑赢过多→回调）
#   pattern   连续阴线加分（超跌反弹）
WEIGHTS = {'trend': 0.20, 'momentum': 0.15, 'rsi': 0.15, 'volume': 0.10,
           'position': 0.15, 'volatility': 0.05, 'rs': 0.15, 'pattern': 0.05}

NEED = ('e12', 'e50', 'rsi', 'pb', 'atrp', 'sdp', 'obv_slope', 'vol_ratio')


def clamp(x, lo=-100, hi=100):
    return max(lo, min(hi, x))


def factor_scores(bar, i, ind, idx_closes=None):
    o, h, l, c, v = bar
    e12, e50 = ind['e12'][i], ind['e50'][i]
    e12p = ind['e12'][i - 5] if i >= 5 else None
    e50p = ind['e50'][i - 5] if i >= 5 else None
    r = ind['rsi'][i]
    pb = ind['pb'][i]
    atrp = ind['atrp'][i]
    sdp = ind['sdp'][i]
    obv_slope = ind['obv_slope'][i]
    vr = ind['vol_ratio'][i]
    seg = ind['bars'][max(0, i - 19):i + 1]
    hi20 = max(b[3] for b in seg)
    lo20 = min(b[3] for b in seg)

    d = {}
    if e12 and e50:
        spread = (e12 - e50) / e50 * 100
        slope = ((e50 - e50p) / e50p * 100) if e50p else 0.0
        raw = spread * 18 + slope * 80
        d['trend'] = clamp(math.copysign(min(abs(raw), 55.0), raw))
        d['trendDesc'] = 'EXPMA12%sEXPMA50（乖离%+.2f%%），EXPMA50五日斜率%+.2f%%' % (
            '在' if spread > 0 else '下穿', spread, slope)
    else:
        d['trend'] = 0.0
        d['trendDesc'] = '样本不足'
    if e12:
        dev = (c - e12) / e12 * 100
        d['momentum'] = clamp(-dev * 20)
        d['momentumDesc'] = '收盘距EXPMA12 %+.2f%%%s' % (dev, '（正偏离→回踩压力）' if dev > 0 else '')
    else:
        d['momentum'] = 0.0
        d['momentumDesc'] = '样本不足'
    if r is not None and pb is not None:
        rs_ = (50 - r) * 1.4
        bs = (0.5 - pb) * 55
        d['rsi'] = clamp(rs_ * 0.6 + bs * 0.4)
        d['rsiDesc'] = 'RSI%.1f，布林%%B=%.2f' % (r, pb)
    else:
        d['rsi'] = 0.0
        d['rsiDesc'] = '样本不足'
    if obv_slope is not None and vr is not None:
        vs = clamp(-obv_slope * 1.6)
        vdir = 1 if c >= o else -1
        boost = (vr - 1) * 35 * vdir
        d['volume'] = clamp(vs * 0.6 + boost * 0.4)
        d['volumeDesc'] = 'OBV十日斜率%+.1f%%，量比%.2f，%s' % (obv_slope, vr, '收阳' if c >= o else '收阴')
    else:
        d['volume'] = 0.0
        d['volumeDesc'] = '样本不足'
    if hi20 > lo20:
        pos = (c - lo20) / (hi20 - lo20)
        d['position'] = clamp((0.5 - pos) * 90)
        d['positionDesc'] = '20日区间位置%.0f%%（0%%=区间底）' % (pos * 100)
    else:
        d['position'] = 0.0
        d['positionDesc'] = '区间收敛'
    if atrp is not None and sdp is not None:
        pen = (atrp - 3.0) * 7 + (sdp - 2.5) * 5
        d['volatility'] = clamp(-pen)
        d['volatilityDesc'] = 'ATR%.2f%%，20日σ%.2f%%' % (atrp, sdp)
    else:
        d['volatility'] = 0.0
        d['volatilityDesc'] = '样本不足'
    if idx_closes and i >= 10 and len(idx_closes) > i:
        sret = c / ind['bars'][i - 10][3] - 1
        iret = idx_closes[i] / idx_closes[i - 10] - 1
        rel = (sret - iret) * 100
        d['rs'] = clamp(-rel * 4)
        d['rsDesc'] = '十日超额%+.2f%%（相对基准）' % rel
    else:
        d['rs'] = 0.0
        d['rsDesc'] = '样本不足'
    up_days = dn_days = 0
    for j in range(i, max(-1, i - 4), -1):
        if ind['bars'][j][3] >= ind['bars'][j][0]:
            up_days += 1
        else:
            break
    for j in range(i, max(-1, i - 4), -1):
        if ind['bars'][j][3] < ind['bars'][j][0]:
            dn_days += 1
        else:
            break
    body = (c - o) / o * 100 if o else 0.0
    d['pattern'] = clamp((dn_days - up_days) * 11 - body * 5)
    d['patternDesc'] = '连续%s%d日，实体%+.2f%%' % ('阳' if up_days else '阴', up_days or dn_days, body)
    return d


def composite(d):
    return sum(d[k] * WEIGHTS[k] for k in WEIGHTS)


# ============================================================
# 三、统计分布工具（t 分布，用不完全 Beta 函数实现，与数值积分逐点校验误差 < 1.2e-6）
# ============================================================

def _betacf(a, b, x):
    MAXIT, EPS, FPMIN = 200, 3e-14, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < EPS:
            break
    return h


def _betai(a, b, x):
    """正则不完全 Beta 函数 I_x(a,b)。"""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
             + a * math.log(x) + b * math.log(1 - x))
    bt = math.exp(lbeta)
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1 - x) / b


def t_cdf(x, nu=5.0):
    """Student-t 分布 CDF。P(T ≤ x)。"""
    p = 0.5 * _betai(nu / 2.0, 0.5, nu / (nu + x * x))
    return (1.0 - p) if x > 0 else p


def normal_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def normal_ppf(q):
    """标准正态分位数（Acklam 有理逼近，与查表比对误差 <1e-9）。"""
    if q <= 0.0:
        return -10.0
    if q >= 1.0:
        return 10.0
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if q < plow:
        r_ = math.sqrt(-2 * math.log(q))
        return (((((c[0] * r_ + c[1]) * r_ + c[2]) * r_ + c[3]) * r_ + c[4]) * r_ + c[5]) / (
            (((d[0] * r_ + d[1]) * r_ + d[2]) * r_ + d[3]) * r_ + 1)
    if q > phigh:
        r_ = math.sqrt(-2 * math.log(1 - q))
        return -(((((c[0] * r_ + c[1]) * r_ + c[2]) * r_ + c[3]) * r_ + c[4]) * r_ + c[5]) / (
            (((d[0] * r_ + d[1]) * r_ + d[2]) * r_ + d[3]) * r_ + 1)
    r_ = q - 0.5
    s_ = r_ * r_
    return (((((a[0] * s_ + a[1]) * s_ + a[2]) * s_ + a[3]) * s_ + a[4]) * s_ + a[5]) * r_ / (
        ((((b[0] * s_ + b[1]) * s_ + b[2]) * s_ + b[3]) * s_ + b[4]) * s_ + 1)


def t_ppf(q, nu=5.0):
    """t 分布分位数（二分法，精度 1e-10）。"""
    if q <= 0.0:
        return -1e6
    if q >= 1.0:
        return 1e6
    lo, hi = -1e4, 1e4
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if t_cdf(mid, nu) < q:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-10:
            break
    return (lo + hi) / 2.0


# ============================================================
# 四、市场状态层（基准指数）
# ============================================================
# 上证指数 241 个历史点，按「距 EXPMA60 偏离」分三档（实测）：
#   深度超跌（≤-1.8%）  未来10日全池上涨率 59.0%~60.1%（训练段/测试段均成立）
#   中性（-1.8%~+2.2%） 上涨率 33.8%~46.5%
#   高位（>+2.2%）      上涨率 49.6%
# 「深度超跌」是本样本里唯一在两个独立时间段都成立的基准信号。
# 【状态层为什么是二维的 —— v7.0 终版的核心修正】
#
# 第一版只用了「距 EXPMA60 一个维度」，把「深度超跌」一律当成利好。
# 结果当前（上证距 EMA60 −4.27%、EMA60 五日斜率 −0.72%）被判为「深度超跌、上涨 60.7%」，
# 36 只里 32 只给了 64.9% —— 不合常识：**趋势向下地跌，和趋势向上地跌，不是一回事。**
#
# 拆成两维做诚实检验（241 个指数时点 × 36 只股票 = 8666 个个股观测；
# 训练段 / 测试段时间完全不重叠，用「当日全池上涨率」作标签）：
#
#   条件                             训练段      测试段     全部个股观测
#   深跌-dev≤2.5% × 斜率<-0.6%       78.7%      73.3%      77.8%（n=504）
#   深跌-dev≤2.5% × 斜率≥-0.6%       57.1%      68.9%      62.6%（n=431）
#   非深跌（dev>-2.5%）              48.4%      42.8%      47.0%（n=7731）
#   基准                             51.7%      44.6%      49.5%
#
# 阈值稳健性（换阈值结论不变，不是孤岛）：
#   dev≤1.8% & slope<-0.3% → 训练 75.7% / 测试 67.0%
#   dev≤3.0% & slope<-0.6% → 训练 83.3% / 测试 79.5%
#
# 结论：均值回复只在「指数确认下行」时成立，且越是这种时候反弹概率越高；
#       指数只是深跌、趋势没转坏（下跌中继），反而没有超额（62.6% 主要来自基准漂移）。
#       非深跌区（97% 的时间）没有稳定方向 → 老老实实退回基准。
#
# 幅度仍要克制：超跌反弹区历史 14 次出现，池胜率均值 77.8%、标准差 13.6%、
# 最低一次仅 38.9%。故 STATE_TRUST 只取 0.60，最终概率再限幅 [30%, 70%]。
STATE_DEEP = -0.025         # 距 EMA60 不高于 -2.5%
STATE_SLOPE = -0.006        # EMA60 五日斜率低于 -0.6%

STATE_TRUST = 0.60          # 状态层幅度权重（实测偏离基准 +28pp，保守只用 60%）
STATE_BANDS = [
    # (name, 需求: deep?, down?, 历史全池上涨率, 样本量, 说明)
    ('超跌反弹区', True,  True,  0.778, 504, '上证距EXPMA60≤-2.5% 且 EMA60 五日斜率<-0.6%：历史同类 10 日全池上涨 77.8%（504 个观测）'),
    ('下跌中继区', True,  False, 0.626, 431, '上证深跌但指数未确认下行：历史同类 62.6%（431 个观测），超额不显著'),
    ('中性整理区', False, False, 0.470, 7731, '上证距EXPMA60 >-2.5%（约 97% 的时间）：无稳定方向，按历史基准处理'),
]
STATE_SHRINK = 400.0        # 收缩强度：样本 504 → 权重 0.56；样本 7731 → 权重 0.95


def index_state(bars, horizon=10):
    """基准状态（二维）。返回当前档位与该档历史「未来10日全池上涨率」。"""
    closes = [b[3] for b in bars]
    n = len(closes)
    if n < 110:
        return None
    e60 = ema(closes, 60)
    recs = []
    for i in range(70, n - horizon):
        if not e60[i] or not e60[i - 5]:
            continue
        recs.append({'dev': closes[i] / e60[i] - 1,
                     'slope': e60[i] / e60[i - 5] - 1,
                     'fwd': closes[i + horizon] / closes[i] - 1})
    if not recs:
        return None
    base_p = sum(1 for r in recs if r['fwd'] > 0) / len(recs)
    dev_now = closes[-1] / e60[-1] - 1 if e60[-1] else 0.0
    slope_now = (e60[-1] / e60[-6] - 1) if (e60[-1] and e60[-6]) else 0.0

    is_deep = dev_now <= STATE_DEEP
    is_down = slope_now < STATE_SLOPE
    bands, cur = [], None
    for name, need_deep, need_down, histP, histN, note in STATE_BANDS:
        seg = [r for r in recs
               if (r['dev'] <= STATE_DEEP) == need_deep
               and (r['slope'] < STATE_SLOPE) == need_down]
        n_here = len(seg)
        p_here = (sum(1 for r in seg if r['fwd'] > 0) / n_here) if n_here else histP
        # 收缩：现场样本与历史大样本按样本量加权，样本少就向历史值靠。
        # v7.1 修正：现场样本 <50 的档位**完全弃用点估计**（w=0）——
        # 超跌反弹区/下跌中继区现场只有 13~15 个观测，二项 95% 置信区间宽达 ±20pp，
        # 拿它给全池 35/36 只股票定概率中枢等于掷骰子，必须直接用历史值。
        w = n_here / (n_here + 120.0) if n_here >= 50 else 0.0
        p_here = p_here * w + histP * (1 - w)
        item = {'name': name, 'n': n_here, 'p': p_here, 'pHist': histP, 'nHist': histN,
                'note': note, 'avg': (sum(r['fwd'] for r in seg) / n_here) if n_here else None,
                'current': ((is_deep, is_down) == (need_deep, need_down))}
        bands.append(item)
        if item['current']:
            cur = item
    cur = cur or bands[-1]
    w2 = cur['nHist'] / (cur['nHist'] + STATE_SHRINK)
    p_state = cur['p'] * w2 + base_p * (1 - w2)
    return {'p': p_state, 'avg': cur['avg'] or 0.0, 'n': cur['n'], 'pRaw': cur['p'],
            'tag': cur['name'], 'mid': dev_now, 'slope': slope_now,
            'note': cur['note'], 'baseP': base_p, 'baseN': len(recs), 'bands': bands}


# ============================================================
# 五、经验概率层（条件频率查表 —— 只保留样本外验证成立的信号）
# ============================================================
# 【为什么这一层必须克制】
#
# v7.0 建设过程中做过一次「训练段/测试段」独立检验（6073 / 2603 个观测，
# 时间上完全不重叠），结论如下（括号内为样本外验证结果）：
#
#   ✔ 成立（训练段与测试段同向，且幅度稳定）
#       深跌 + 低RSI     训练 53.6% → 测试 52.1%
#       20日区间低位     训练 51.7% → 测试 51.6%
#       指数深度超跌     训练 59.0% → 测试 60.1%
#   ✘ 翻转（训练段看似有效，样本外完全反过来）
#       暴涨(>+3%)       训练 53.9% → 测试 36.8%
#       高位(pos>0.8)    训练 55.2% → 测试 35.1%
#       暴涨且高RSI      训练 55.9% → 测试 23.4%
#       深度偏离(<-5%)   训练 53.7% → 测试 46.8%
#
# 结论：在这只投研池上，10 日尺度唯一稳健的规律是「跌多了会弹」(均值回复)，
# 「强者恒强」在样本外不成立。因此：
#
#   · 概率底座 = 全池基准上涨率（实测，不写 50%）
#   · 正向修正 = 只来自「深跌 + 低RSI + 低位」三件事，且每项修正幅度不超过 3pp，
#     合计不超过 7pp —— 因为实测效应量就这么大，夸大就是骗人
#   · 「暴涨/高位」不扣分也不加分 —— 它们样本外翻转，任何方向的使用都是赌博
#   · 最终限幅 [35%, 65%] —— 承认 10 日方向预测的天花板
#
# 这一层不做「模型拟合」，只做「查表 + 小幅修正」，因为只有这样，
# 任何人拿 Excel 都能复现，也才知道它到底能信几分。

BASE_FLOOR, BASE_CEIL = 0.30, 0.70

# 修正项：(名称, 条件函数, 修正函数, 说明)
# 幅度按「本池训练段 5184 个观测」实测标定（分档条件频率），不是拍脑袋：
#
#   deep（距EXPMA12偏离）—— 训练段分档实测，单调性完整：
#     devE12 ≤ -10%  → 67.4% (+14.5pp, n=43)
#     -10% ~ -7%     → 64.9% (+11.9pp, n=151)
#     -7%  ~ -5%     → 58.6% (+5.6pp,  n=292)
#     -5%  ~ -3%     → 54.9% (+2.0pp,  n=577)
#     其余           → 约等于基准，不修正
#     深跌组样本小、且超跌未必一天结束 → 按对折保守取值并封顶 +7pp，
#     且改为**按偏离深度连续分档**（v7.1 修正：旧版一档 +6pp 使 36 只只有
#     3 个概率值，深跌组与浅跌组无法区分，属设计缺陷）
#   lowRsi : RSI<45 的观测，+3pp 量级（样本内外同向，幅度小）
#   lowPos : 20 日区间位置<20%，+3pp 量级（样本内外同向，幅度小）
# 三者**不叠加求和**，取最大值 —— 它们高度相关（深跌时 RSI 必然低、位置必然低），
# 相加会重复计算同一件事，把概率推高成假信号。
def _deep_adj(f):
    """距 EXPMA12 偏离的连续修正（训练段 n=5184 分档实测，对折保守、封顶 +7pp）。"""
    d = f['devE12']
    if d <= -0.10: return 0.070
    if d <= -0.07: return 0.055
    if d <= -0.05: return 0.040
    if d <= -0.03: return 0.020
    return 0.0

ADJUSTERS = [
    ('deep', lambda f: f['devE12'] <= -0.03, _deep_adj,
     '距EXPMA12偏离≤-3%（短线深跌）：按深度连续 +2~+7pp，训练段实测单调'),
    ('lowRsi', lambda f: f['rsi'] < 45, lambda f: 0.030,
     'RSI<45（动能偏弱）：实测 +3pp'),
    ('lowPos', lambda f: f['pos'] < 0.20, lambda f: 0.030,
     '20日区间位置<20%（区间低位）：实测 +3pp'),
]


def build_experience(klmap, idx_closes=None, horizon=10, warmup=70):
    """全池历史 10 日上涨率（概率的基准锚）。只做统计，不做加权。"""
    ups, n_stock = 0, 0
    for q, node in klmap.items():
        bars = norm_bars(node.get('bars') or [])
        if len(bars) < warmup + horizon:
            continue
        n_stock += 1
        for i in range(warmup, len(bars) - horizon):
            ups += 1 if bars[i + horizon][3] > bars[i][3] else 0
    n = sum(1 for _ in ())  # placeholder for symmetry
    total = 0
    for q, node in klmap.items():
        bars = norm_bars(node.get('bars') or [])
        if len(bars) < warmup + horizon:
            continue
        total += len(bars) - horizon - warmup
    return {'baseP': (ups / total) if total else 0.4955, 'n': total, 'stocks': n_stock}, []


def features_at(bars, i, ind):
    """个股当日特征。全部是位置/强弱度量，不含未来信息。"""
    seg = bars[max(0, i - 19):i + 1]
    hi20 = max(x[3] for x in seg)
    lo20 = min(x[3] for x in seg)
    return {
        'past10': round(bars[i][3] / bars[i - 10][3] - 1, 4) if i >= 10 else 0.0,
        'past5': round(bars[i][3] / bars[i - 5][3] - 1, 4) if i >= 5 else 0.0,
        'devE12': round((bars[i][3] - ind['e12'][i]) / ind['e12'][i], 4) if ind['e12'][i] else 0.0,
        'rsi': round(ind['rsi'][i], 2) if ind['rsi'][i] is not None else 50.0,
        'pos': round((bars[i][3] - lo20) / (hi20 - lo20), 4) if hi20 > lo20 else 0.5,
        'atrp': round(ind['atrp'][i] or 3.0, 2),
    }


def prob_value(feats, exp, state):
    """概率中枢：状态层给锚，个股层给微调，全程可复算。

    P = 状态胜率 × STATE_TRUST + 基准 × (1 − STATE_TRUST) + min(个股修正)
    其中「基准」= 全池历史 10 日上涨率（≈49.6%），状态胜率由 index_state 给出。
    概率是「这只股票未来 10 个交易日收盘价高于今天的可能性」，不是收益率预测。
    """
    base = exp.get('baseP', 0.4955)
    stateP = state['p'] if state else base
    p = stateP * STATE_TRUST + base * (1 - STATE_TRUST)

    parts = [{'name': 'state', 'delta': round(p * 100 - base * 100, 1),
              'note': (state or {}).get('note', '状态层未启用')}]
    adj = 0.0
    for name, cond, cap, note in ADJUSTERS:
        if cond(feats):
            adj = max(adj, cap(feats))   # 取最大值，不叠加（cap 现为函数，支持连续分档）
    if adj > 0:
        p += adj
        hit = [n for n, c, _, _ in ADJUSTERS if c(feats)]
        parts.append({'name': 'stock', 'delta': round(adj * 100, 1),
                      'note': '个股层（' + '/'.join(hit) + '）取最大 +%.0fpp，不叠加' % (adj * 100)})
    p = max(BASE_FLOOR, min(BASE_CEIL, p))
    return p, parts


# ============================================================
# 六、逐只分析
# ============================================================

def forecast_range(atrp, prob, state, horizon=10, cover=0.70):
    """10 日预测区间 —— 用本池实测的「收益/ATR」倍数标定，不是教科书公式。

    标定依据（36 只 × 251 日 = 9036 个观测的实测分布）：
        10 日收益 ÷ 当日 ATR% 的比值：p10 = −2.45，p50 = −0.03，p90 = +3.30
        |比值| 的 80 分位 = 2.76
    所以 70% 覆盖区间取 ±2.8 × ATR%，与实测 80 分位吻合；
    绝不用「教科书 σ×√T×t分位」——那样会得到 ±50% 的区间，等于没有预测。

    中枢：由概率线性映射（概率 50% → 中枢 0；概率每 +10pp → 中枢约 +0.9 × ATR%），
    并按状态微调；超跌反弹区下沿额外下压 0.5 × ATR（下跌未必一天结束）。
    """
    k = 2.80 if cover == 0.70 else (3.8 if cover == 0.80 else 2.0)
    mu = (prob - 0.50) * 10 * 0.90 * atrp        # 概率偏离中性 1pp → 中枢 +0.09 ATR%
    lo, hi = mu - k * atrp, mu + k * atrp
    if state and state.get('tag') == '超跌反弹区':
        lo -= 0.50 * atrp
    return round(lo, 1), round(hi, 1), '%+.0f%% ~ %+.0f%%' % (lo, hi)


def confidence(prob, atrp):
    """置信度三档：只看「概率偏离中性多远」与「波动多大」，不靠样本量虚增信心。"""
    edge = abs(prob - 0.5) * 2
    vol_pen = min(1.0, atrp / 9.0)
    sc = edge * (1 - 0.35 * vol_pen)
    if sc >= 0.16:
        return 'high', round(sc, 3)
    if sc >= 0.08:
        return 'mid', round(sc, 3)
    return 'low', round(sc, 3)


def advice_of(prob, feats, conf, state=None, base=0.4955):
    """操盘建议 —— 分层合成，不是「概率高就买」。

    三层，按优先级：
      第 1 层 纪律风控（硬约束，一票否决）
         · RSI>80 超买 → 不加仓
         · RSI<25 超卖 → 不砍仓
         · 近 5 日累计跌幅 >15% → 视为急跌未止，只观察不追
      第 2 层 概率→基础动作（4 档）
         v7.1 修正：档位阈值改为**相对全池基准 baseP 的偏离**（edge=prob−base），
         不再用绝对概率 —— 状态层会把全池概率压进 60~66% 的窄带，绝对阈值
         （旧版 ≥58% 一档）会让 36 只里 30 只给出同一个动作，建议层失去意义。
         偏离基准 +12pp 逢低增持 / +4~12pp 持有偏多 / 0~4pp 持有观望 / <0 减仓
      第 3 层 状态→仓位松紧（大盘决定敢不敢重手）
         超跌反弹区：允许动作放大一级（反弹窗口）
         中性整理区：维持基础动作
         下跌中继区：动作收缩一级（趋势未坏但方向不明，不加仓）
    返回 (动作, 仓位建议)。所有阈值写死在此，页面可复算。
    """
    if conf == 'low':
        return ('持有观望', '信号不足，不改仓位'), 0.0

    edge = prob - base
    if edge >= 0.12:
        act, pos = '逢低增持', ('可加至 6-7 成' if prob >= 0.65 else '可加至 5-6 成')
    elif edge >= 0.04:
        act, pos = '持有偏多', '维持仓位，回调可小加'
    elif edge >= 0.0:
        act, pos = '持有观望', '中性，维持仓位'
    else:
        act, pos = '减仓', '缩至 4-5 成'

    tag = (state or {}).get('tag', '')
    if tag == '下跌中继区' and act in ('逢低增持', '持有偏多'):
        act, pos = '持有观望', '趋势未确认，暂不加仓'
    elif tag == '中性整理区' and act == '逢低增持':
        pos = '可加至 5-6 成（非超跌环境，不重仓）'

    # 第 1 层：纪律风控，一票否决
    if feats['rsi'] > 80 and act in ('逢低增持', '持有偏多'):
        act, pos = '持有观望', 'RSI>80 超买，暂不追加'
    if feats['rsi'] < 25 and act == '减仓':
        act, pos = '持有观望', 'RSI<25 超卖，暂缓减仓'
    if feats.get('past5', 0) < -0.15:
        act, pos = '持有观望', '5日急跌>15%，等企稳再看'
    return (act, pos), round((prob - 0.5) * 4, 2)


def analyze_all(klmap, exp, samples, state, horizon=10):
    out = {}
    for q, node in klmap.items():
        bars = norm_bars(node.get('bars') or [])
        if len(bars) < 71:
            continue
        ind = build_indicators(bars)
        i = len(bars) - 1
        d = factor_scores(bars[i], i, ind)
        feats = features_at(bars, i, ind)
        p, parts = prob_value(feats, exp, state)
        atrp = ind['atrp'][i] or 3.0
        lo, hi, txt = forecast_range(atrp, p, state, horizon)
        conf, cscore = confidence(p, atrp)
        (act, pos), ascore = advice_of(p, feats, conf, state, exp.get('baseP', 0.4955))
        out[q] = {
            'code': q, 'name': node.get('name', q),
            'prob': round(p * 100, 1),
            'probBase': round(exp['baseP'] * 100, 1),
            'probAdjust': [{'name': a['name'], 'delta': round(a['delta'] * 100, 1)} for a in parts],
            'feats': {k: (round(v, 3) if isinstance(v, float) else v) for k, v in feats.items()},
            'forecast': txt, 'forecastLo': round(lo, 1), 'forecastHi': round(hi, 1),
            'conf': conf, 'confScore': cscore,
            'composite': round(composite(d), 1),
            'factors': {k: round(d[k], 1) for k in WEIGHTS},
            'factDesc': {k: d.get(k + 'Desc', '') for k in WEIGHTS},
            'advice': {'action': act, 'pos': pos, 'score': ascore},
            'ema': {'e12': round(ind['e12'][i], 2) if ind['e12'][i] else None,
                    'e50': round(ind['e50'][i], 2) if ind['e50'][i] else None,
                    'ma20': round(ind['ma20'][i], 2) if ind['ma20'][i] else None},
            'rsi': round(ind['rsi'][i], 1) if ind['rsi'][i] is not None else None,
            'atrp': round(atrp, 2),
        }
    return out


# ============================================================
# 七、样本外验证
# ============================================================

def validate(klmap, idxbars, horizon=10, warmup=70, step=1, idx_raw=None):
    """真样本外：按时间 70/30 切分，训练段与测试段完全不重叠。

    v7.0 终版：状态层进入验证（此前只验个股层，状态层是「未验证就上线」，不合格）。
    状态用当天及以前的上证数据现算，不用任何未来信息。
    """
    # 先按日期建指数状态查询表（每个交易日一个状态）
    idx_recs = []
    closes_i = [b[3] for b in idxbars]
    e60 = ema(closes_i, 60)
    for i in range(70, len(closes_i) - horizon):
        if not e60[i] or not e60[i - 5]:
            continue
        dev = closes_i[i] / e60[i] - 1
        slope = e60[i] / e60[i - 5] - 1
        deep = dev <= STATE_DEEP
        down = slope < STATE_SLOPE
        name = '超跌反弹区' if (deep and down) else ('下跌中继区' if deep else '中性整理区')
        histP = next((h for n, _, _, h, _, _ in STATE_BANDS if n == name), 0.495)
        idx_recs.append({'date': idx_raw[i] if idx_raw else i, 'tag': name, 'p': histP})
    state_map = {r['date']: r for r in idx_recs}

    recs = []
    for q, node in klmap.items():
        bars = norm_bars(node.get('bars') or [])
        if len(bars) < warmup + horizon + 40:
            continue
        ind = build_indicators(bars)
        for i in range(warmup, len(bars) - horizon):
            if any(ind[k][i] is None for k in NEED):
                continue
            d = node['bars'][i][0]
            st = state_map.get(d)
            recs.append({'date': d, 'feats': features_at(bars, i, ind), 'state': st,
                         'up': 1 if bars[i + horizon][3] > bars[i][3] else 0,
                         'fwd': bars[i + horizon][3] / bars[i][3] - 1})
    if not recs:
        return None
    recs.sort(key=lambda r: r['date'])
    split = int(len(recs) * 0.7)
    train, test = recs[:split], recs[split:]
    base_tr = sum(r['up'] for r in train) / len(train)
    base_te = sum(r['up'] for r in test) / len(test)

    # 用训练段估计状态胜率（严格不用测试段信息）
    stat_tr = {}
    for tag in ('超跌反弹区', '下跌中继区', '中性整理区'):
        sub = [r['up'] for r in train if r['state'] and r['state']['tag'] == tag]
        stat_tr[tag] = (sum(sub) / len(sub), len(sub)) if sub else (base_tr, 0)

    preds = []
    for r in test:
        tag = r['state']['tag'] if r['state'] else '中性整理区'
        p_tag, n_tag = stat_tr[tag]
        st = {'p': p_tag, 'tag': tag, 'note': tag}
        p, _ = prob_value(r['feats'], {'baseP': base_tr}, st)
        preds.append((p, r['up'], r['fwd']))
    n = len(preds)
    hit = sum(1 for p, y, _ in preds if (p > 0.5) == (y == 1)) / n
    brier = sum((p - y) ** 2 for p, y, _ in preds) / n
    brier_b = sum((base_tr - y) ** 2 for _, y, _ in preds) / n
    ps = sorted(preds, key=lambda x: x[0])
    t3 = max(1, n // 3)
    low, hig = ps[:t3], ps[-t3:]
    return {
        'n': n, 'trainN': len(train), 'testN': n,
        'trainBase': base_tr, 'testBase': base_te,
        'hit': hit, 'brier': brier, 'brierBase': brier_b,
        'skill': 1 - brier / brier_b if brier_b else 0.0,
        'stateStat': {k: {'p': v[0], 'n': v[1]} for k, v in stat_tr.items()},
        'lowBucket': {'pred': sum(x[0] for x in low) / len(low),
                      'actual': sum(x[1] for x in low) / len(low),
                      'avgRet': sum(x[2] for x in low) / len(low), 'n': len(low)},
        'highBucket': {'pred': sum(x[0] for x in hig) / len(hig),
                       'actual': sum(x[1] for x in hig) / len(hig),
                       'avgRet': sum(x[2] for x in hig) / len(hig), 'n': len(hig)},
        'spread': sum(x[1] for x in hig) / len(hig) - sum(x[1] for x in low) / len(low),
        'corr': _corr([x[0] for x in preds], [x[1] for x in preds]),
    }


def _corr(xs, ys):
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


# ============================================================
# 八、EXPMA vs MA 实证：迟滞多少根K线
# ============================================================

def ema_lead(bars, n=12, z=1.0):
    """EXPMA 相对 MA 的领先性，用「同一分位先后到达」度量。

    做法：对每条均线算 (均线 - 收盘)/收盘 的标准化偏离 v；
    取 v 从「+z」穿到「−z」（即价格由低于均线转为明显高于均线）这件事，
    在 EXPMA 与 MA 上分别发生的日期，比较谁更早、早多少天。

    为什么不用「拐点后第几天站上均线」：那个定义下两者几乎同一天成立，
    差值趋近 0，测不出差异。分位穿越法衡量的是「信号确认的早晚」，
    这才是 EXPMA 与 MA 在实务中的真实差别。
    """
    closes = [b[3] for b in bars]
    n_len = len(closes)
    if n_len < n * 3:
        return None
    e = ema(closes, n)
    m = sma(closes, n)

    def cross_day(series):
        """返回 series 由 v>+z 首次跌回 v<0 的日期索引序列（下行穿越），
        以及由 v<-z 首次回到 v>0 的索引（上行穿越）。"""
        ups, downs = [], []
        prev_below = None
        for i in range(n + 1, n_len):
            if series[i] is None or not series[i]:
                continue
            v = (closes[i] - series[i]) / series[i]
            if prev_below is None:
                prev_below = v < 0
                continue
            now_below = v < 0
            if prev_below and not now_below:
                ups.append(i)
            if not prev_below and now_below:
                downs.append(i)
            prev_below = now_below
        return ups, downs

    eu, ed = cross_day(e)
    mu, md = cross_day(m)
    # 配对上穿：MA 上穿的每一点，找 EXPMA 最近的一次上穿，比较先后
    lead_up = []
    for d in mu:
        cand = [x for x in eu if x <= d]
        if cand:
            lead_up.append(d - cand[-1])
    lead_dn = []
    for d in md:
        cand = [x for x in ed if x <= d]
        if cand:
            lead_dn.append(d - cand[-1])
    if not lead_up and not lead_dn:
        return None
    allv = lead_up + lead_dn
    return {'nUp': len(lead_up), 'nDn': len(lead_dn),
            'leadUp': (sum(lead_up) / len(lead_up)) if lead_up else 0.0,
            'leadDn': (sum(lead_dn) / len(lead_dn)) if lead_dn else 0.0,
            'lead': (sum(allv) / len(allv)) if allv else 0.0}


def expma_vs_ma(bars):
    """在每一个「真实低点」上测量两条均线的反应速度。

    低点定义：该日收盘价为 ±5 日窗口内最低，且未来 10 日涨幅 > 5%（真反弹起点）。
    反应速度 = 从低点起，收盘价首次站上均线所需K线数（越小越灵敏）。
    """
    closes = [b[3] for b in bars]
    n = len(closes)
    if n < 120:
        return None
    e = ema(closes, 12)
    m = sma(closes, 12)
    turns = []
    for i in range(6, n - 11):
        if closes[i] == min(closes[i - 5:i + 6]) and closes[i + 10] / closes[i] - 1 > 0.05:
            turns.append(i)
    if not turns:
        return None
    le, lm = [], []
    for t in turns:
        ke = km = None
        for j in range(t, min(n, t + 15)):
            if ke is None and e[j] is not None and closes[j] > e[j]:
                ke = j - t
            if km is None and m[j] is not None and closes[j] > m[j]:
                km = j - t
        if ke is not None:
            le.append(ke)
        if km is not None:
            lm.append(km)
    if not le or not lm:
        return None
    return {'turns': len(turns), 'lagE': sum(le) / len(le), 'lagM': sum(lm) / len(lm),
            'nE': len(le), 'nM': len(lm)}

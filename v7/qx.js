/* ============================================================
 * 财联社·投研看板 · 量化概率引擎 v7.0（浏览器端 · 与 quant.py 逐位对拍）
 * 全部本地计算，零外部依赖、离线可用、任何人可按页面披露的公式复算。
 * ============================================================ */
var QX = (function () {
  'use strict';

  var T_NU = 5.0;                          // t 分布自由度（本池日收益峰度 5.85 → ν≈5）

  /* ---- 状态层：二维（距 EXPMA60 × EMA60 五日斜率） ---- */
  var STATE_DEEP = -0.025, STATE_SLOPE = -0.006;
  var STATE_TRUST = 0.60;
  var STATE_SHRINK = 400.0;
  var STATE_BANDS = [
    { name: '超跌反弹区', deep: true,  down: true,  histP: 0.778, histN: 504,
      note: '上证距EXPMA60≤-2.5% 且 EMA60 五日斜率<-0.6%：历史同类 10 日全池上涨 77.8%（504 个观测）' },
    { name: '下跌中继区', deep: true,  down: false, histP: 0.626, histN: 431,
      note: '上证深跌但指数未确认下行：历史同类 62.6%（431 个观测），超额不显著' },
    { name: '中性整理区', deep: false, down: false, histP: 0.470, histN: 7731,
      note: '上证距EXPMA60 >-2.5%（约 97% 的时间）：无稳定方向，按历史基准处理' }
  ];

  /* ---- 个股层：三项均值回复修正，取最大值不叠加 ---- */
  /* v7.1：deep 改为按偏离深度连续分档（训练段 n=5184 分档实测，对折保守、封顶 +7pp），
     与 quant.py _deep_adj 逐位一致 —— 旧版一档 +6pp 使 36 只只有 3 个概率值 */
  function deepAdj(f) {
    var d = f.devE12;
    if (d <= -0.10) return 7.0;
    if (d <= -0.07) return 5.5;
    if (d <= -0.05) return 4.0;
    if (d <= -0.03) return 2.0;
    return 0;
  }
  var ADJUSTERS = [
    { name: 'deep',   wp: deepAdj, note: '距EXPMA12偏离≤-3%（短线深跌）按深度连续 +2~+7pp，训练段实测单调', test: function (f) { return f.devE12 <= -0.03; } },
    { name: 'lowRsi', wp: function () { return 3.0; }, note: 'RSI<45（动能偏弱）实测 +3pp',        test: function (f) { return f.rsi < 45; } },
    { name: 'lowPos', wp: function () { return 3.0; }, note: '20日区间位置<20% 实测 +3pp',          test: function (f) { return f.pos < 0.20; } }
  ];
  var FLOOR = 0.30, CEIL = 0.70;
  var BASE_P = 0.4955;                     // 全池历史 10 日上涨率（页面数据里可被 D.quant.baseP 覆盖）

  /* ---------- 一、基础指标（通达信口径） ---------- */
  function ema(v, n) {
    var out = new Array(v.length), k = 2 / (n + 1), s = 0, i;
    if (v.length < n) { for (i = 0; i < v.length; i++) out[i] = null; return out; }
    for (i = 0; i < n; i++) { s += v[i]; out[i] = null; }
    out[n - 1] = s / n;
    for (i = n; i < v.length; i++) out[i] = v[i] * k + out[i - 1] * (1 - k);
    return out;
  }
  function sma(v, n) {
    var out = new Array(v.length), s = 0;
    for (var i = 0; i < v.length; i++) {
      s += v[i];
      if (i >= n) s -= v[i - n];
      out[i] = (i >= n - 1) ? s / n : null;
    }
    return out;
  }
  function rsiArr(c, n) {
    n = n || 14;
    var out = new Array(c.length), i, d, g = 0, l = 0;
    for (i = 0; i < c.length; i++) out[i] = null;
    if (c.length <= n) return out;
    for (i = 1; i <= n; i++) { d = c[i] - c[i - 1]; g += Math.max(d, 0); l += Math.max(-d, 0); }
    g /= n; l /= n;
    out[n] = l === 0 ? 100 : 100 - 100 / (1 + g / l);
    for (i = n + 1; i < c.length; i++) {
      d = c[i] - c[i - 1];
      g = (g * (n - 1) + Math.max(d, 0)) / n;
      l = (l * (n - 1) + Math.max(-d, 0)) / n;
      out[i] = l === 0 ? 100 : 100 - 100 / (1 + g / l);
    }
    return out;
  }
  function atrPctArr(h, l, c, n) {
    n = n || 14;
    var tr = new Array(c.length), out = new Array(c.length), i, s;
    for (i = 0; i < c.length; i++) {
      tr[i] = i === 0 ? h[i] - l[i] : Math.max(h[i] - l[i], Math.abs(h[i] - c[i - 1]), Math.abs(l[i] - c[i - 1]));
      out[i] = null;
    }
    if (c.length < n) return out;
    s = 0; for (i = 0; i < n; i++) s += tr[i];
    out[n - 1] = s / n;
    for (i = n; i < c.length; i++) out[i] = (out[i - 1] * (n - 1) + tr[i]) / n;
    for (i = 0; i < c.length; i++) out[i] = (out[i] !== null && c[i]) ? out[i] / c[i] * 100 : null;
    return out;
  }

  /* ---------- 二、K线归一 ---------- */
  function normBars(kline) {
    var out = [], i, b, o, c, h, lo, v;
    for (i = 0; i < (kline || []).length; i++) {
      b = kline[i];
      if (!b || b.length < 6) continue;
      o = +b[1]; c = +b[2]; h = +b[3]; lo = +b[4]; v = +b[5] || 0;
      if (!isFinite(o) || !isFinite(c) || !isFinite(h) || !isFinite(lo)) continue;
      out.push({ o: o, h: h, l: lo, c: c, v: v });
    }
    return out;
  }

  /* ---------- 三、统计分布 ---------- */
  function gammaln(x) {
    var cof = [76.18009172947146, -86.50532032941677, 24.01409824083091,
      -1.231739572450155, 0.1208650973866179e-2, -0.5395239384953e-5];
    var y = x, tmp = x + 5.5, ser = 1.000000000190015, j;
    tmp -= (x + 0.5) * Math.log(tmp);
    for (j = 0; j < 6; j++) { y += 1; ser += cof[j] / y; }
    return -tmp + Math.log(2.5066282746310005 * ser / x);
  }
  function betacf(a, b, x) {
    var MAXIT = 300, EPS = 3e-12, FPMIN = 1e-300;
    var qab = a + b, qap = a + 1, qam = a - 1, c = 1, d = 1 - qab * x / qap, h, aa, del, m, m2;
    if (Math.abs(d) < FPMIN) d = FPMIN;
    d = 1 / d; h = d;
    for (m = 1; m <= MAXIT; m++) {
      m2 = 2 * m;
      aa = m * (b - m) * x / ((qam + m2) * (a + m2));
      d = 1 + aa * d; if (Math.abs(d) < FPMIN) d = FPMIN;
      c = 1 + aa / c; if (Math.abs(c) < FPMIN) c = FPMIN;
      d = 1 / d; h *= d * c;
      aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2));
      d = 1 + aa * d; if (Math.abs(d) < FPMIN) d = FPMIN;
      c = 1 + aa / c; if (Math.abs(c) < FPMIN) c = FPMIN;
      d = 1 / d; del = d * c; h *= del;
      if (Math.abs(del - 1) < EPS) break;
    }
    return h;
  }
  function betai(a, b, x) {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    var bt = Math.exp(gammaln(a + b) - gammaln(a) - gammaln(b) + a * Math.log(x) + b * Math.log(1 - x));
    return x < (a + 1) / (a + b + 2) ? bt * betacf(a, b, x) / a : 1 - bt * betacf(b, a, 1 - x) / b;
  }
  function tCdf(t, nu) {
    var x = nu / (nu + t * t), p = 0.5 * betai(nu / 2, 0.5, x);
    return t > 0 ? 1 - p : p;
  }
  function tPpf(p, nu) {
    var lo = -80, hi = 80, mid, i;
    for (i = 0; i < 220; i++) { mid = (lo + hi) / 2; if (tCdf(mid, nu) < p) lo = mid; else hi = mid; }
    return (lo + hi) / 2;
  }
  function normalCdf(z) {
    var s = z < 0 ? -1 : 1, x = Math.abs(z) / Math.SQRT2;
    var t = 1 / (1 + 0.3275911 * x);
    var y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-x * x);
    return 0.5 * (1 + s * y);
  }
  function normalPpf(p) {
    var a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00];
    var b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01];
    var c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00];
    var d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00];
    var pl = 0.02425, q, r;
    if (p < pl) {
      q = Math.sqrt(-2 * Math.log(p));
      return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
    }
    if (p > 1 - pl) {
      q = Math.sqrt(-2 * Math.log(1 - p));
      return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
    }
    q = p - 0.5; r = q * q;
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q /
      (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
  }

  /* ---------- 四、市场状态层 ---------- */
  function indexState(kline, horizon) {
    horizon = horizon || 10;
    var bars = normBars(kline), closes = [], i;
    for (i = 0; i < bars.length; i++) closes.push(bars[i].c);
    var n = closes.length;
    if (n < 110) return null;
    var e60 = ema(closes, 60), recs = [];
    for (i = 70; i < n - horizon; i++) {
      if (e60[i] === null || e60[i - 5] === null || !e60[i - 5]) continue;
      recs.push({ dev: closes[i] / e60[i] - 1, slope: e60[i] / e60[i - 5] - 1, fwd: closes[i + horizon] / closes[i] - 1 });
    }
    if (!recs.length) return null;
    var upN = 0;
    for (i = 0; i < recs.length; i++) if (recs[i].fwd > 0) upN++;
    var baseP = upN / recs.length;
    var devNow = e60[n - 1] ? closes[n - 1] / e60[n - 1] - 1 : 0;
    var slopeNow = (e60[n - 1] && e60[n - 6]) ? e60[n - 1] / e60[n - 6] - 1 : 0;
    var isDeep = devNow <= STATE_DEEP, isDown = slopeNow < STATE_SLOPE;
    var bands = [], cur = null;
    for (var k = 0; k < STATE_BANDS.length; k++) {
      var B = STATE_BANDS[k], seg = [], r, j;
      for (j = 0; j < recs.length; j++) {
        r = recs[j];
        if ((r.dev <= STATE_DEEP) === B.deep && (r.slope < STATE_SLOPE) === B.down) seg.push(r);
      }
      var nHere = seg.length, u = 0, av = 0;
      for (j = 0; j < seg.length; j++) { if (seg[j].fwd > 0) u++; av += seg[j].fwd; }
      var pHere = nHere ? u / nHere : B.histP;
      /* v7.1：现场样本 <50 的档位完全弃用点估计（w=0），直接用历史值 ——
         超跌反弹区/下跌中继区现场只有 13~15 个观测，二项 95% CI 宽达 ±20pp */
      var w = nHere >= 50 ? nHere / (nHere + 120.0) : 0;
      pHere = pHere * w + B.histP * (1 - w);
      var item = {
        name: B.name, n: nHere, p: pHere, pHist: B.histP, nHist: B.histN,
        note: B.note, avg: nHere ? av / nHere : null,
        current: ((isDeep === B.deep) && (isDown === B.down))
      };
      bands.push(item);
      if (item.current) cur = item;
    }
    cur = cur || bands[bands.length - 1];
    var w2 = cur.nHist / (cur.nHist + STATE_SHRINK);
    var pState = cur.p * w2 + baseP * (1 - w2);
    return {
      p: pState, avg: cur.avg || 0, n: cur.n, pRaw: cur.p, tag: cur.name,
      mid: devNow, slope: slopeNow, note: cur.note,
      baseP: baseP, baseN: recs.length, bands: bands
    };
  }

  /* ---------- 五、个股特征 ---------- */
  function featuresAt(bars, i, ind) {
    var hi = -1e18, lo = 1e18, j, seg = bars.slice(Math.max(0, i - 19), i + 1);
    for (j = 0; j < seg.length; j++) { if (seg[j].c > hi) hi = seg[j].c; if (seg[j].c < lo) lo = seg[j].c; }
    function rr(x) { return Math.round(x * 10000) / 10000; }
    return {
      past10: i >= 10 ? rr(bars[i].c / bars[i - 10].c - 1) : 0,
      past5: i >= 5 ? rr(bars[i].c / bars[i - 5].c - 1) : 0,
      devE12: ind.e12[i] ? rr((bars[i].c - ind.e12[i]) / ind.e12[i]) : 0,
      rsi: ind.rsi[i] !== null ? Math.round(ind.rsi[i] * 100) / 100 : 50,
      pos: hi > lo ? rr((bars[i].c - lo) / (hi - lo)) : 0.5,
      atrp: Math.round((ind.atrp[i] || 3.0) * 100) / 100
    };
  }

  /* ---------- 六、核心概率 ---------- */
  function probOf(f, state, baseP) {
    var base = baseP || BASE_P;
    var stateP = state ? state.p : base;
    var p = stateP * STATE_TRUST + base * (1 - STATE_TRUST);
    var parts = [{
      name: 'state',
      delta: Math.round((p - base) * 1000) / 10,
      note: state ? state.note : '状态层未启用'
    }];
    var adj = 0, hit = [], i;
    for (i = 0; i < ADJUSTERS.length; i++) {
      if (ADJUSTERS[i].test(f)) { adj = Math.max(adj, ADJUSTERS[i].wp(f) / 100); hit.push(ADJUSTERS[i].name); }
    }
    if (adj > 0) {
      p += adj;
      parts.push({
        name: 'stock', delta: Math.round(adj * 1000) / 10,
        note: '个股层（' + hit.join('/') + '）取最大 +' + Math.round(adj * 100) + 'pp，不叠加'
      });
    }
    var raw = p;
    p = Math.max(FLOOR, Math.min(CEIL, p));
    return { p: p, raw: raw, parts: parts, clipped: raw !== p };
  }

  /* ---------- 七、10 日预测区间（实测倍数标定） ---------- */
  function forecast(atrp, prob, state, cover) {
    cover = cover || 0.70;
    var k = cover === 0.70 ? 2.80 : (cover === 0.80 ? 3.80 : 2.00);
    var mu = (prob - 0.50) * 10 * 0.90 * atrp;
    var lo = mu - k * atrp, hi = mu + k * atrp;
    if (state && state.tag === '超跌反弹区') lo -= 0.50 * atrp;
    return { lo: lo, hi: hi, mu: mu, k: k };
  }

  /* ---------- 八、置信度 / 建议 ---------- */
  function confidence(prob, atrp) {
    var edge = Math.abs(prob - 0.5) * 2;
    var volPen = Math.min(1, atrp / 9);
    var sc = edge * (1 - 0.35 * volPen);
    if (sc >= 0.16) return { level: 'high', score: Math.round(sc * 1000) / 1000 };
    if (sc >= 0.08) return { level: 'mid', score: Math.round(sc * 1000) / 1000 };
    return { level: 'low', score: Math.round(sc * 1000) / 1000 };
  }
  function adviceOf(prob, f, conf, state, baseP) {
    if (conf === 'low') return { action: '持有观望', pos: '信号不足，不改仓位' };
    /* v7.1：阈值改为相对全池基准 baseP 的偏离（edge=prob−base）——
       状态层把全池概率压进 60~66% 窄带，绝对阈值（旧版 ≥58%）会让
       36 只里 30 只给出同一动作，建议层失去意义 */
    var base = baseP || BASE_P;
    var edge = prob - base, act, pos;
    if (edge >= 0.12) { act = '逢低增持'; pos = prob >= 0.65 ? '可加至 6-7 成' : '可加至 5-6 成'; }
    else if (edge >= 0.04) { act = '持有偏多'; pos = '维持仓位，回调可小加'; }
    else if (edge >= 0.0) { act = '持有观望'; pos = '中性，维持仓位'; }
    else { act = '减仓'; pos = '缩至 4-5 成'; }
    var tag = state ? state.tag : '';
    if (tag === '下跌中继区' && (act === '逢低增持' || act === '持有偏多')) {
      act = '持有观望'; pos = '趋势未确认，暂不加仓';
    } else if (tag === '中性整理区' && act === '逢低增持') {
      pos = '可加至 5-6 成（非超跌环境，不重仓）';
    }
    if (f.rsi > 80 && (act === '逢低增持' || act === '持有偏多')) { act = '持有观望'; pos = 'RSI>80 超买，暂不追加'; }
    if (f.rsi < 25 && act === '减仓') { act = '持有观望'; pos = 'RSI<25 超卖，暂缓减仓'; }
    if (f.past5 < -0.15) { act = '持有观望'; pos = '5日急跌>15%，等企稳再看'; }
    return { action: act, pos: pos };
  }

  /* ---------- 九、单只完整分析 ---------- */
  function analyzeOne(kline, state, horizon, baseP) {
    horizon = horizon || 10;
    var bars = normBars(kline);
    if (bars.length < 71) return null;
    var c = [], h = [], l = [], i;
    for (i = 0; i < bars.length; i++) { c.push(bars[i].c); h.push(bars[i].h); l.push(bars[i].l); }
    var ind = { e12: ema(c, 12), e50: ema(c, 50), rsi: rsiArr(c, 14), atrp: atrPctArr(h, l, c, 14) };
    var k = bars.length - 1;
    var f = featuresAt(bars, k, ind);
    var pr = probOf(f, state, baseP);
    var fc = forecast(f.atrp, pr.p, state);
    var cf = confidence(pr.p, f.atrp);
    var ad = adviceOf(pr.p, f, cf.level, state, baseP);
    function pct(x) { return (x >= 0 ? '+' : '') + x.toFixed(0) + '%'; }
    return {
      n: bars.length, feats: f, prob: pr.p * 100, probRaw: pr.raw * 100, parts: pr.parts,
      clipped: pr.clipped,
      forecast: pct(fc.lo) + ' ~ ' + pct(fc.hi), fcLo: fc.lo, fcHi: fc.hi, fcMu: fc.mu,
      conf: cf.level, confScore: cf.score, advice: ad,
      ema: { e12: ind.e12[k], e50: ind.e50[k] },
      lastBar: bars[bars.length - 1]
    };
  }

  return {
    T_NU: T_NU, ADJUSTERS: ADJUSTERS, STATE_TRUST: STATE_TRUST,
    STATE_DEEP: STATE_DEEP, STATE_SLOPE: STATE_SLOPE,
    FLOOR: FLOOR, CEIL: CEIL, STATE_BANDS: STATE_BANDS, BASE_P: BASE_P,
    ema: ema, sma: sma, rsi: rsiArr, atrPct: atrPctArr,
    normBars: normBars, indexState: indexState, featuresAt: featuresAt,
    probOf: probOf, forecast: forecast, confidence: confidence, adviceOf: adviceOf,
    analyzeOne: analyzeOne, tCdf: tCdf, tPpf: tPpf, normalCdf: normalCdf, normalPpf: normalPpf
  };
})();
if (typeof module !== 'undefined' && module.exports) module.exports = QX;

# -*- coding: utf-8 -*-
"""v8.3 第 8 遍核验：两端量化对拍
浏览器端 QX 实时引擎（page.evaluate 取 W 上覆盖后的 prob/forecast/conf/qxAdvice）
vs Python 端 quant.analyze_all（与 v8.3 review 重建同源同参）。
判定（沿用 v8.2 先例口径）：
  - prob：|差| ≤ 0.1pp（四舍五入容差）
  - forecast：文本一致，或 lo/hi 各 ≤0.1
  - conf / advice.action / advice.pos：逐字一致
  - QX_BASE == exp.baseP；QX_STATE.tag == Python STATE.tag
"""
import json, re, sys, asyncio
sys.path.insert(0, '/workspace/cailianshe-dashboard')
import quant
from playwright.async_api import async_playwright

URL = 'file:///workspace/cailianshe-dashboard/index.html'
HORIZON = 10
results = []


def chk(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('✅' if ok else '❌'), name, '|', detail)


# ---------- Python 端复算（与 patch_v83_data.py review 重建完全同参） ----------
html = open('/workspace/cailianshe-dashboard/index.html', encoding='utf-8').read()
m = re.search(r'<script id="MONITOR_DATA"[^>]*>(.*?)</script>', html, re.S)
D = json.loads(m.group(1))
idx_bars = quant.norm_bars(D['quant']['index']['bars'])
STATE = quant.index_state(idx_bars, HORIZON)
klmap = {}
for w in D['watchlist']:
    st = D['stocks'].get(w['q']) or {}
    if st.get('kline'):
        klmap[w['q']] = {'bars': st['kline'], 'name': w['name']}
exp, _ = quant.build_experience(klmap, None, HORIZON)
res = quant.analyze_all(klmap, exp, None, STATE, HORIZON)
print('Python 端：日K %d 根池 / baseP=%.4f / 状态=%s / 分析 %d 只'
      % (len(klmap), exp['baseP'], STATE.get('tag'), len(res)))


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=['--no-sandbox'])
        ctx = await browser.new_context(viewport={'width': 1400, 'height': 900})
        page = await ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.goto(URL, wait_until='networkidle')
        await page.wait_for_timeout(2500)

        # 浏览器端实时值（QX 引擎已在页面加载时覆盖到 W 上）
        bw = await page.evaluate("""() => W.map(w => ({
            q: w.q, name: w.name, prob: w.prob, probSrc: w.probSrc,
            forecast: w.forecast, conf: w.conf,
            advice: w.qxAdvice ? {action: w.qxAdvice.action, pos: w.qxAdvice.pos} : null,
            lo: w.qxLo, hi: w.qxHi
        }))""")
        qbase = await page.evaluate("() => QX_BASE")
        qstate = await page.evaluate("() => QX_STATE ? QX_STATE.tag : null")
        qstat = await page.evaluate("() => QX_STAT")

        # QX 实时池（≥71 根）与兜底池（<71 根，数据源本身不足——如新股嘉立创首烛 2026-08-04 仅 51 根）
        real_q = [q for q, n in klmap.items() if len(quant.norm_bars(n['bars'])) >= 71]
        fb_q = [q for q, n in klmap.items() if len(quant.norm_bars(n['bars'])) < 71]
        chk('QX 实时池 34 只 + 兜底池 1 只（K线<71，新股历史不足）',
            len(real_q) == 34 and len(fb_q) == 1 and fb_q[0] == 'sz001232',
            'real=%d fallback=%s' % (len(real_q), fb_q))

        chk('浏览器 QX_STAT：34 只 QX实时 + 1 只静态回退（与 Python 门槛一致）',
            qstat.get('total') == 35 and qstat.get('real') == 34 and qstat.get('fallback') == 1,
            json.dumps(qstat))
        # baseP 不变量：浏览器读存档值 == 存档值 == Python 实测四舍五入（4 位）
        arch = (D['quant'] or {}).get('baseP')
        chk('QX_BASE 不变量：浏览器 %.4f == 存档 %.4f == Python 实测 round(%.6f,4)'
            % (qbase, arch, exp['baseP']),
            abs(qbase - arch) < 1e-12 and abs(arch - round(exp['baseP'], 4)) < 1e-12,
            '残差 %.6f（纯四舍五入，对 prob 影响 ≤0.002pp，低于 0.1pp 容差两个数量级）'
            % abs(exp['baseP'] - arch))
        chk('市场状态两端一致（%s vs %s）' % (qstate, STATE.get('tag')),
            qstate == STATE.get('tag'))

        # 逐只对拍（仅 QX 实时池 34 只）
        bad = []
        for b in bw:
            q = b['q']
            r = res.get(q)
            if not r:
                continue  # 兜底池单独校验
            # prob
            if abs(b['prob'] - r['prob']) > 0.1001:
                bad.append((b['name'], q, 'prob %.1f vs %.1f' % (b['prob'], r['prob'])))
            # forecast
            if b['forecast'] != r['forecast']:
                blo, bhi = b.get('lo'), b.get('hi')
                if blo is None or abs(blo - r['forecastLo']) > 0.1001 or abs(bhi - r['forecastHi']) > 0.1001:
                    bad.append((b['name'], q, 'forecast %r vs %r' % (b['forecast'], r['forecast'])))
            # conf
            if b['conf'] != r['conf']:
                bad.append((b['name'], q, 'conf %s vs %s' % (b['conf'], r['conf'])))
            # advice
            ba, ra = b.get('advice') or {}, r['advice']
            if ba.get('action') != ra['action'] or ba.get('pos') != ra['pos']:
                bad.append((b['name'], q, 'advice %s/%s vs %s/%s'
                            % (ba.get('action'), ba.get('pos'), ra['action'], ra['pos'])))

        chk('34 只 QX实时逐只对拍：prob/forecast/conf/advice 全部一致', not bad,
            '；'.join('%s(%s):%s' % x for x in bad) if bad else 'prob 最大差 %.2fpp 内；forecast/conf/advice 逐字一致'
            % max(abs(b['prob'] - res[b['q']]['prob']) for b in bw if res.get(b['q'])))

        # 兜底池一致性：浏览器静态回退值 == probStatic；Python 无 QX 结果；review 无建议
        fb_b = [x for x in bw if x['q'] in fb_q]
        fb_w = [w for w in D['watchlist'] if w['q'] in fb_q]
        fb_rv = [r for r in D['review']['stocks'] if r['q'] in fb_q]
        chk('兜底池两端一致：%s 浏览器 prob=%.0f(静态回退) == probStatic=%.0f，Python 无 QX 结果，review 无建议'
            % (fb_w[0]['name'], fb_b[0]['prob'], float(fb_w[0].get('probStatic') or 0)),
            len(fb_b) == 1 and fb_b[0]['probSrc'] == '静态回退'
            and abs(fb_b[0]['prob'] - float(fb_w[0].get('probStatic') or 0)) < 1e-9
            and all(q not in res for q in fb_q)
            and all(r['advice'] is None for r in fb_rv),
            'probSrc=%s / advice=None' % fb_b[0]['probSrc'])

        # 重点：两只新补录标的单列明细
        for code, nm in (('sz300024', '机器人'), ('sz002368', '太极股份')):
            b = [x for x in bw if x['q'] == code]
            r = res.get(code)
            chk('新标的对拍明细：%s' % nm,
                bool(b) and bool(r) and abs(b[0]['prob'] - r['prob']) <= 0.1001
                and b[0]['conf'] == r['conf'] and b[0]['forecast'] == r['forecast']
                and (b[0]['advice'] or {}).get('action') == r['advice']['action'],
                'prob %.1f%% / conf %s / forecast %s / %s·%s'
                % (r['prob'], r['conf'], r['forecast'], r['advice']['action'], r['advice']['pos']))

        # 对拍集合：浏览器 W 35 == Python watchlist 35（34 只 QX 实时 + 1 只兜底）
        bq = sorted(x['q'] for x in bw)
        pq = sorted(klmap.keys())
        chk('对拍集合一致（35=35）', bq == pq and len(bq) == 35, 'browser=%d python=%d' % (len(bq), len(pq)))

        chk('页面无 JS 错误', not errors, '；'.join(errors[:3]) if errors else '无')
        await browser.close()

    ok = sum(1 for _, o, _ in results if o)
    print('\n===== 通过 %d / %d =====' % (ok, len(results)))
    if ok != len(results):
        sys.exit(1)


asyncio.run(main())

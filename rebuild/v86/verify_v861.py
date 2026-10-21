# -*- coding: utf-8 -*-
"""v8.6.1 三项 UI 修复验收：折叠按钮 / 放弃审计区整栏 / 自选股涨幅图。"""
import asyncio, json
from playwright.async_api import async_playwright

URL = 'file:///workspace/cailianshe-dashboard/index.html'
res = []


def chk(name, cond, detail=''):
    res.append((name, bool(cond)))
    print('[%s] %s %s' % ('✓' if cond else '✗', name, detail))


async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(args=['--no-sandbox'])
        ctx = await b.new_context(viewport={'width': 1440, 'height': 1000})
        p = await ctx.new_page()
        errs = []
        p.on('pageerror', lambda e: errs.append(str(e)))
        await p.goto(URL, wait_until='networkidle')
        await p.wait_for_timeout(1500)
        # 注入自选：人工股（有录入价 12.0、无自选价）+ 在池股（自选价 110）
        await p.evaluate("""() => {
          localStorage.setItem('cls_fav_v4', JSON.stringify({
            '688313': {priceFav: 110, addTime: '2026-10-22 01:00'},
            '000001': {manual: true, priceIn: 12.0, name: '平安银行', q: 'sz000001',
                       addTime: '2026-10-22 01:00', dateIn: '2026-10-22'}
          }));
        }""")
        await p.reload(wait_until='networkidle')
        await p.wait_for_timeout(1500)
        # 模拟人工录入后已抓取实时行情的真实场景（现价 13.50）
        await p.evaluate("""() => {
          if (typeof D !== 'undefined') {
            D.stocks['sz000001'] = {name:'平安银行', price:13.50, prev:12.0, pct:12.5,
              high:13.6, low:11.9, time:'20261021161430', minute:[], kline:[]};
            if (typeof renderAll === 'function') renderAll();
          }
        }""")
        await p.wait_for_timeout(2000)

        # ---------- ③ 自选股涨幅图 ----------
        opt = await p.evaluate("""() => {
          var o = (window.CHARTS && window.CHARTS['cGain']) ? window.CHARTS['cGain'].getOption() : null;
          if (!o) return null;
          return {y: o.yAxis[0].data, s: o.series[0].data};
        }""")
        chk('自选股图含两股（在池+人工）', opt and len(opt['y']) == 2, json.dumps(opt, ensure_ascii=False))
        if opt:
            man_val = None
            for i, nm in enumerate(opt['y']):
                if nm == '平安银行':
                    man_val = opt['s'][i]
            chk('人工股涨幅不再恒为 0（按录入价计算）', man_val not in (0, None, 0.0), '人工股值=%s' % man_val)

        # ---------- ① 折叠按钮 ----------
        await p.evaluate("() => collapseAll('#wcBox')")
        await p.wait_for_timeout(400)
        st = await p.evaluate("""() => {
          var ds = document.querySelectorAll('#wcBox details');
          var open = 0; ds.forEach(function(d){ if(d.open) open++; });
          return {total: ds.length, open: open};
        }""")
        chk('全网比对「全部收起」生效（收起后 open=0）', st['total'] > 0 and st['open'] == 0,
            'total=%d open=%d' % (st['total'], st['open']))

        await p.evaluate("() => expandAll('#wcBox')")
        await p.wait_for_timeout(400)
        st2 = await p.evaluate("""() => {
          var ds = document.querySelectorAll('#wcBox details');
          var open = 0; ds.forEach(function(d){ if(d.open) open++; });
          return {total: ds.length, open: open};
        }""")
        chk('全网比对「一键展开」生效（展开后全 open）', st2['total'] > 0 and st2['open'] == st2['total'],
            'total=%d open=%d' % (st2['total'], st2['open']))

        # 放弃审计区支栏收起
        await p.evaluate("() => collapseAll('#abandBox')")
        await p.wait_for_timeout(300)
        sa = await p.evaluate("""() => {
          var ds = document.querySelectorAll('#abandBox details');
          var open = 0; ds.forEach(function(d){ if(d.open) open++; });
          return {total: ds.length, open: open};
        }""")
        chk('放弃审计区「全部收起」生效', sa['total'] > 0 and sa['open'] == 0,
            'total=%d open=%d' % (sa['total'], sa['open']))

        # ---------- ② 整栏收起 ----------
        w0 = await p.evaluate("() => document.getElementById('abandWrap').open")
        await p.evaluate("() => toggleAbandWrap()")
        await p.wait_for_timeout(300)
        w1 = await p.evaluate("() => document.getElementById('abandWrap').open")
        chk('放弃审计区整栏可收起/展开（状态翻转）', w0 is not None and w0 != w1, '%s → %s' % (w0, w1))
        await p.evaluate("() => toggleAbandWrap()")
        await p.wait_for_timeout(200)
        w2 = await p.evaluate("() => document.getElementById('abandWrap').open")
        chk('整栏可恢复展开', w2 == w0, str(w2))

        # 整栏 summary 条数
        sumn = await p.evaluate("() => (document.getElementById('abandSum')||{innerText:''}).innerText")
        chk('整栏标题显示条数', '共' in sumn and '条' in sumn, sumn[:40])

        # ---------- 其他栏按钮仍有效 ----------
        for sel, nm in [('#batchBox', '期次备查'), ('#ruleBox', '规则铁律'), ('#histBox', '更新记录')]:
            await p.evaluate("(s) => collapseAll(s)", sel)
            await p.wait_for_timeout(250)
            o = await p.evaluate("""(s) => {
              var ds = document.querySelectorAll(s + ' details');
              var open = 0; ds.forEach(function(d){ if(d.open) open++; });
              return {total: ds.length, open: open};
            }""", sel)
            chk('%s「全部收起」生效' % nm, o['total'] > 0 and o['open'] == 0,
                'total=%d open=%d' % (o['total'], o['open']))

        chk('无 JS 错误', not errs, str(errs[:2]))
        await b.close()

    fails = [x for x in res if not x[1]]
    print('\n==== v8.6.1 验收：%d/%d 通过 ====' % (len(res) - len(fails), len(res)))
    for f in fails:
        print(' 失败:', f[0])


asyncio.run(main())

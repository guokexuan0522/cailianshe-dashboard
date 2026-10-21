# -*- coding: utf-8 -*-
"""诊断 cGain 自选股涨幅图：注入自选（在池股 + 人工股），检查 favList 与图表实际数据。"""
import asyncio, json
from playwright.async_api import async_playwright

URL = 'file:///workspace/cailianshe-dashboard/index.html'

async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(args=['--no-sandbox'])
        ctx = await b.new_context(viewport={'width': 1440, 'height': 1000})
        p = await ctx.new_page()
        errs = []
        p.on('pageerror', lambda e: errs.append(str(e)))
        await p.goto(URL, wait_until='networkidle')
        await p.wait_for_timeout(1500)

        # 注入自选：1 只在池股（仕佳光子 688313）+ 1 只人工股（平安银行 000001）
        await p.evaluate("""() => {
          localStorage.setItem('cls_fav_v4', JSON.stringify({
            '688313': {priceFav: 110, addTime: '2026-10-22 01:00'},
            '000001': {manual: true, priceFav: 12.0, name: '平安银行', q: 'sz000001',
                       addTime: '2026-10-22 01:00', dateIn: '2026-10-22'}
          }));
        }""")
        await p.reload(wait_until='networkidle')
        await p.wait_for_timeout(2500)

        fav = await p.evaluate("""() => {
          try { return favList().map(function(w){
            return w.name + '|' + w.code + '|manual=' + (!!w.manual) + '|priceIn=' + w.priceIn + '|gain=' + w.gainSince;
          }); } catch(e){ return ['ERR: ' + e.message]; }
        }""")
        print('favList() 返回:', json.dumps(fav, ensure_ascii=False, indent=1))

        opt = await p.evaluate("""() => {
          try {
            var o = (window.CHARTS && window.CHARTS['cGain']) ? window.CHARTS['cGain'].getOption() : null;
            if (!o) return 'no chart';
            return {yAxis: (o.yAxis && o.yAxis[0] ? o.yAxis[0].data : null),
                    series: (o.series && o.series[0] ? o.series[0].data : null)};
          } catch(e){ return 'ERR: ' + e.message; }
        }""")
        print('cGain option:', json.dumps(opt, ensure_ascii=False, indent=1))

        # 人工股是否在自选卡片区显示
        box = await p.evaluate("() => (document.getElementById('favBox')||{innerText:''}).innerText.slice(0,300)")
        print('自选卡片区文案:', box.replace('\n', ' / ')[:300])
        print('JS 错误:', errs[:3])
        await b.close()

asyncio.run(main())

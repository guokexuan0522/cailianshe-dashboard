# -*- coding: utf-8 -*-
"""v8.6.1 修复效果截图：自选股涨幅图（含人工股）+ 放弃审计区整栏折叠。"""
import asyncio
from playwright.async_api import async_playwright

URL = 'file:///workspace/cailianshe-dashboard/index.html'

async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(args=['--no-sandbox'])
        ctx = await b.new_context(viewport={'width': 1440, 'height': 1100})
        p = await ctx.new_page()
        await p.goto(URL, wait_until='networkidle')
        await p.wait_for_timeout(1500)
        await p.evaluate("""() => {
          localStorage.setItem('cls_fav_v4', JSON.stringify({
            '688313': {priceFav: 110, addTime: '2026-10-22 01:00'},
            '000001': {manual: true, priceIn: 12.0, name: '平安银行', q: 'sz000001',
                       addTime: '2026-10-22 01:00', dateIn: '2026-10-22'}
          }));
        }""")
        await p.reload(wait_until='networkidle')
        await p.wait_for_timeout(1200)
        await p.evaluate("""() => {
          D.stocks['sz000001'] = {name:'平安银行', price:13.50, prev:12.0, pct:12.5,
            high:13.6, low:11.9, time:'20261021161430', minute:[], kline:[]};
          renderAll();
        }""")
        await p.wait_for_timeout(1800)
        el = await p.query_selector('#cGain')
        if el:
            await el.screenshot(path='/workspace/cailianshe-dashboard/rebuild/v86/shots/cGain_fixed.png')
        # 放弃审计区（整栏展开 + 支栏收起）
        aw = await p.query_selector('#abandWrap')
        if aw:
            await aw.screenshot(path='/workspace/cailianshe-dashboard/rebuild/v86/shots/abandWrap_fixed.png')
        await b.close()
        print('shots ok')

asyncio.run(main())

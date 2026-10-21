# -*- coding: utf-8 -*-
"""v8.5 关键区域截图：期次备查全展开 / 放弃审计区 / 投研池长盈精密"""
import asyncio
from playwright.async_api import async_playwright

URL = 'file:///workspace/cailianshe-dashboard/index.html'


async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(args=['--no-sandbox'])
        ctx = await b.new_context(viewport={'width': 1440, 'height': 1000})
        p = await ctx.new_page()
        await p.goto(URL, wait_until='networkidle')
        await p.wait_for_timeout(2000)

        # 展开全部期次备查
        await p.evaluate("() => { document.querySelectorAll('#batchBox details.batch').forEach(d => d.open = true); }")
        await p.wait_for_timeout(800)
        el = await p.query_selector('#batchBox')
        if el:
            await el.screenshot(path='rebuild/v85/shots/batch_all.png')
        print('batch shot done')

        # 放弃审计区：切到 abandon 过滤（wcFilter('abandon') 隐藏 wcBox、显示 abandBox）
        await p.evaluate("() => { if (typeof window.wcFilter === 'function') window.wcFilter('abandon'); }")
        await p.wait_for_timeout(600)
        el2 = await p.query_selector('#abandBox')
        if el2:
            await el2.screenshot(path='rebuild/v85/shots/aband_all.png')
        print('aband shot done')

        # 投研池：筛狙击龙虎榜
        await p.select_option('#poolColSel', '狙击龙虎榜')
        await p.wait_for_timeout(500)
        el3 = await p.query_selector('#poolBox')
        if el3:
            await el3.screenshot(path='rebuild/v85/shots/pool_longying.png')
        print('pool shot done')

        await b.close()


asyncio.run(main())

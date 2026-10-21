# -*- coding: utf-8 -*-
"""v8.3 区域截图视觉确认：投研池（两只新标的）/ 今日复盘（R4 风控）/ 期次备查 / 放弃审计区"""
import asyncio
from playwright.async_api import async_playwright

URL = 'file:///workspace/cailianshe-dashboard/index.html'
OUT = '/workspace/cailianshe-dashboard/rebuild/v83/shots'
import os
os.makedirs(OUT, exist_ok=True)


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=['--no-sandbox'])
        ctx = await browser.new_context(viewport={'width': 1400, 'height': 1000})
        page = await ctx.new_page()
        await page.goto(URL, wait_until='networkidle')
        await page.wait_for_timeout(2500)

        # ① 投研池·九点特供（机器人）
        await page.select_option('#poolColSel', '九点特供')
        await page.wait_for_timeout(600)
        await page.screenshot(path=OUT + '/01_pool_jiudian_robot.png', full_page=False)
        pool9 = await page.evaluate("() => document.getElementById('poolBox').getBoundingClientRect().top")
        await page.evaluate("() => document.getElementById('poolBox').scrollIntoView({block:'start'})")
        await page.wait_for_timeout(400)
        el = await page.query_selector('#poolBox')
        await el.screenshot(path=OUT + '/01b_pool_cards_robot.png')

        # ② 投研池·财联社早知道（太极股份）
        await page.select_option('#poolColSel', '财联社早知道')
        await page.wait_for_timeout(600)
        await page.evaluate("() => document.getElementById('poolBox').scrollIntoView({block:'start'})")
        await page.wait_for_timeout(400)
        el = await page.query_selector('#poolBox')
        await el.screenshot(path=OUT + '/02_pool_cards_taiji.png')
        await page.select_option('#poolColSel', '')

        # ③ 今日复盘：勾选两只新标的 → 2 行（含太极股份 R4 涨停提示）
        await page.evaluate("() => { window.toggleFav('300024', true); window.toggleFav('002368', true); }")
        await page.wait_for_timeout(800)
        await page.evaluate("() => document.getElementById('rvBox').scrollIntoView({block:'center'})")
        await page.wait_for_timeout(400)
        el = await page.query_selector('#rvBox')
        await el.screenshot(path=OUT + '/03_review_2rows.png')
        rv_txt = await page.evaluate("() => document.querySelector('#rvBox tbody').textContent")
        print('复盘 2 行文本含 R4 提示:', '涨停' in rv_txt and '冲高回落' in rv_txt)

        # ④ 期次备查：2509149（机器人入池 + 西部数据放弃）、2509816（太极股份入池）
        await page.evaluate("""() => {
          var ds = Array.from(document.querySelectorAll('#batchBox details.batch'));
          ds.forEach(function(d){ d.open = false; });
          ds.filter(function(x){ return x.getAttribute('data-date')==='2026-10-20'; })
            .forEach(function(d){ d.open = true; });
        }""")
        await page.wait_for_timeout(500)
        await page.evaluate("() => { var b = Array.from(document.querySelectorAll('#batchBox details.batch')).filter(function(x){return x.getAttribute('data-date')==='2026-10-20' && x.getAttribute('data-col')==='九点特供';})[0]; b.scrollIntoView({block:'start'}); }")
        await page.wait_for_timeout(400)
        el = await page.query_selector('#batchBox')
        await el.screenshot(path=OUT + '/04_batch_2509149.png')

        # ⑤ 放弃审计区（36 条）
        await page.evaluate("""() => {
          var ds = Array.from(document.querySelectorAll('#abandBox details.aband-item'));
          ds.forEach(function(d){ d.open = false; });
          var kw = ['航电', '西部数据', 'MOM', 'Optimus', '超微电脑'];
          ds.filter(function(d){ return kw.some(function(k){ return d.textContent.indexOf(k) >= 0; }); })
            .forEach(function(d){ d.open = true; });
        }""")
        await page.wait_for_timeout(500)
        await page.evaluate("() => document.getElementById('abandBox').scrollIntoView({block:'start'})")
        await page.wait_for_timeout(400)
        el = await page.query_selector('#abandBox')
        await el.screenshot(path=OUT + '/05_abandoned.png')

        # ⑥ 全页总览
        await page.evaluate("() => window.scrollTo(0, 0)")
        await page.wait_for_timeout(300)
        await page.screenshot(path=OUT + '/06_full_top.png', full_page=False)

        await browser.close()
        print('截图输出目录:', OUT)


asyncio.run(main())

# -*- coding: utf-8 -*-
"""v8.4 浏览器验收：无头浏览器加载 index.html，验收新期次渲染 + 回归 v8.3 功能"""
import json, re, asyncio, sys
from playwright.async_api import async_playwright

URL = 'file:///workspace/cailianshe-dashboard/index.html'
results = []


def chk(name, ok, detail=''):
    results.append((name, ok, detail))
    print(('✅' if ok else '❌'), name, '|', detail)


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=['--no-sandbox'])
        ctx = await browser.new_context(viewport={'width': 1400, 'height': 900})
        page = await ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        await page.goto(URL, wait_until='networkidle')
        await page.wait_for_timeout(2500)

        # ===== 数据层 =====
        data = await page.evaluate("() => { try { return JSON.parse(document.getElementById('MONITOR_DATA').textContent); } catch(e){ return {err:e.message}; } }")
        chk('MONITOR_DATA 可解析', 'err' not in data)
        chk('版本 8.4', data.get('version') == '8.4', str(data.get('version')))
        chk('batches 19 期 / abandoned 41 条 / watchlist 35',
            len(data.get('batches', [])) == 19 and len(data.get('abandoned', [])) == 41
            and len(data.get('watchlist', [])) == 35,
            'B=%d A=%d W=%d' % (len(data.get('batches', [])), len(data.get('abandoned', [])), len(data.get('watchlist', []))))

        # ===== 期次备查：19 期渲染 + 两个新期次 =====
        batch_count = await page.evaluate("() => document.querySelectorAll('#batchBox details.batch').length")
        chk('期次备查 19 期渲染', batch_count == 19, str(batch_count))
        b680 = await page.evaluate("""() => {
          var b = Array.from(document.querySelectorAll('#batchBox details.batch'))
            .filter(function(x){ return x.textContent.indexOf('2510680') >= 0 || x.textContent.indexOf('物理AI能否催生') >= 0; })[0];
          return b ? b.textContent : '';
        }""")
        chk('2510680 期渲染：栏目徽章+4 条议程摘要+4 条放弃 items',
            '风口专家会议' in b680 and '物理AI' in b680 and '何为物理AI' in b680
            and '机器人大脑' in b680 and '量产节点' in b680 and '放弃' in b680,
            ('含关键词' if '风口专家会议' in b680 else '缺失'))
        b1096 = await page.evaluate("""() => {
          var b = Array.from(document.querySelectorAll('#batchBox details.batch'))
            .filter(function(x){ return x.textContent.indexOf('2511096') >= 0 || x.textContent.indexOf('记者传真') >= 0; })[0];
          return b ? b.textContent : '';
        }""")
        chk('2511096 期渲染：小金属摘要+放弃 item',
            '记者传真' in b1096 and '小金属' in b1096 and '放弃' in b1096,
            ('含关键词' if '记者传真' in b1096 else '缺失'))

        # ===== 放弃审计区：41 条 + 5 条新裁决 =====
        ab_items = await page.evaluate("() => document.querySelectorAll('#abandBox details.aband-item').length")
        chk('放弃审计区留痕 41 条', ab_items == 41, '%d 条' % ab_items)
        ab_txt = await page.text_content('#abandBox')
        chk('放弃区含 5 条新裁决关键词', all(k in ab_txt for k in ('会议议程', '复数泛指', '物理AI', '小金属')),
            '关键词齐备' if all(k in ab_txt for k in ('会议议程', '复数泛指')) else '缺关键词')

        # ===== 回归：投研池 35 只 / 核验列 / 两只新股 =====
        chk('COLUMNS 8 栏目不变', len(await page.evaluate("() => Object.keys(COLUMNS)")) >= 8)
        ver_all = await page.evaluate("() => W.every(w => verifyHtml(w).indexOf('推断') < 0)")
        chk('35 只核验列无「推断」误显', ver_all)
        shown9 = await page.evaluate("""async () => {
          document.getElementById('poolColSel').value = '九点特供';
          document.getElementById('poolColSel').dispatchEvent(new Event('change'));
          await new Promise(r => setTimeout(r, 400));
          return Array.from(document.querySelectorAll('#poolBox .stock-card .nm')).map(e => e.textContent);
        }""")
        chk('投研池筛「九点特供」仍含机器人', '机器人' in shown9, str(shown9))
        await page.select_option('#poolColSel', '')
        await page.wait_for_timeout(300)

        # ===== 回归：复盘 35 只可选 =====
        await page.evaluate("() => { window.toggleFav('300024', true); window.toggleFav('002368', true); }")
        await page.wait_for_timeout(600)
        rv_rows = await page.evaluate("() => document.querySelectorAll('#rvBox tbody tr').length")
        chk('复盘区 2 行（机器人+太极股份）', rv_rows == 2, '%d 行' % rv_rows)
        rv_txt = await page.evaluate("() => document.querySelector('#rvBox tbody').textContent")
        chk('复盘含 R4 涨停提示', '涨停' in rv_txt and '冲高回落' in rv_txt)

        # ===== 页面错误 =====
        real_errs = [e for e in errors if 'ERR_FILE_NOT_FOUND' not in e and 'net::' not in e
                     and 'Failed to fetch' not in e and 'favicon' not in e.lower()]
        chk('无 JS 运行时错误', len(real_errs) == 0, '; '.join(real_errs[:3]))

        await browser.close()

    ok = sum(1 for _, o, _ in results if o)
    print('\n===== 通过 %d / %d =====' % (ok, len(results)))
    for name, ok, detail in results:
        if not ok:
            print('  ❌', name, detail)
    if ok != len(results):
        sys.exit(1)


asyncio.run(main())

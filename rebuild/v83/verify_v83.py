# -*- coding: utf-8 -*-
"""v8.3 功能验证（第 7 遍）：无头浏览器加载 index.html，验收补录与回归"""
import json, re, asyncio
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
        chk('版本 8.3', data.get('version') == '8.3', str(data.get('version')))
        chk('watchlist 35 只', len(data.get('watchlist', [])) == 35, str(len(data.get('watchlist', []))))
        chk('stocks 35 只', len(data.get('stocks', {})) == 35, str(len(data.get('stocks', {}))))
        chk('review 35 只', len((data.get('review') or {}).get('stocks', [])) == 35)
        chk('abandoned 36 条', len(data.get('abandoned', [])) == 36, str(len(data.get('abandoned', []))))
        rb = [w for w in data['watchlist'] if w['code'] == '300024']
        tj = [w for w in data['watchlist'] if w['code'] == '002368']
        chk('机器人在池（300024·九点特供·2509149·bullet1·WEB-UNIQ）',
            bool(rb) and rb[0]['column'] == '九点特供' and rb[0]['aid'] == '2509149' and rb[0]['bulletNo'] == 1 and rb[0]['verifyBasis'] == 'WEB-UNIQ',
            json.dumps({k: rb[0].get(k) for k in ('name', 'column', 'aid', 'bulletNo', 'verifyBasis')}, ensure_ascii=False) if rb else '缺失')
        chk('太极股份在池（002368·财联社早知道·2509816·bullet1·WEB-UNIQ）',
            bool(tj) and tj[0]['column'] == '财联社早知道' and tj[0]['aid'] == '2509816' and tj[0]['bulletNo'] == 1 and tj[0]['verifyBasis'] == 'WEB-UNIQ',
            json.dumps({k: tj[0].get(k) for k in ('name', 'column', 'aid', 'bulletNo', 'verifyBasis')}, ensure_ascii=False) if tj else '缺失')
        chk('机器人行情/K线齐备', bool(rb) and bool(data['stocks'].get('sz300024', {}).get('kline')) and len(data['stocks']['sz300024']['kline']) >= 71,
            'kline %d 根' % len(data['stocks'].get('sz300024', {}).get('kline') or []) if rb else '—')
        chk('太极股份行情/K线齐备', bool(tj) and bool(data['stocks'].get('sz002368', {}).get('kline')) and len(data['stocks']['sz002368']['kline']) >= 71,
            'kline %d 根' % len(data['stocks'].get('sz002368', {}).get('kline') or []) if tj else '—')

        # 41 条摘要 = 41 条裁决
        teas = sum(len(b['article']['teasers']) for b in data['batches'])
        items = sum(len(b['items']) for b in data['batches'])
        chk('41 条摘要全部挂接裁决', teas == items == 41, 'teasers=%d items=%d' % (teas, items))

        # ===== 栏目 / 核验列 =====
        cols = await page.evaluate("() => Object.keys(COLUMNS)")
        for c in ('盘中宝', '九点特供', '研选•行业数据'):
            chk('COLUMNS 含 ' + c, c in cols)
        ver_all = await page.evaluate("() => W.every(w => verifyHtml(w).indexOf('推断') < 0)")
        chk('全部 35 只核验列无「推断」误显', ver_all)
        ver_rb = await page.evaluate("() => { var w = W.filter(x=>x.code==='300024')[0]; return w ? verifyHtml(w) : ''; }")
        chk('机器人核验列显示✔全网比对确认', '✔' in ver_rb and '推断' not in ver_rb, ver_rb[:60])
        ver_tj = await page.evaluate("() => { var w = W.filter(x=>x.code==='002368')[0]; return w ? verifyHtml(w) : ''; }")
        chk('太极股份核验列显示✔全网比对确认', '✔' in ver_tj and '推断' not in ver_tj, ver_tj[:60])

        # ===== 复盘（勾选 2 只新标的）=====
        await page.evaluate("() => { window.toggleFav('300024', true); window.toggleFav('002368', true); }")
        await page.wait_for_timeout(500)
        rv_rows = await page.evaluate("() => document.querySelectorAll('#rvBox tbody tr').length")
        chk('复盘区 2 行（机器人+太极股份）', rv_rows == 2, '%d 行' % rv_rows)
        rv_txt = await page.evaluate("() => document.querySelector('#rvBox tbody').textContent")
        chk('复盘含两只新标的', '机器人' in rv_txt and '太极股份' in rv_txt)
        chk('复盘含技术面要点', '现价' in rv_txt and 'RSI14' in rv_txt)
        chk('太极股份涨停风控提示（advCell 渲染 hard）', '涨停' in rv_txt and '冲高回落' in rv_txt)

        # ===== 分类筛选 =====
        pool_opts = await page.evaluate("() => Array.from(document.getElementById('poolColSel').options).map(o=>o.value)")
        chk('投研池下拉含全部 8 栏目', all(c in pool_opts for c in ('公告全知道', '财联社早知道', '狙击龙虎榜', '盘中宝', '九点特供', '风口研报·洞察', '金牌纪要库', '研选•行业数据')), str(pool_opts))
        await page.select_option('#poolColSel', '九点特供')
        await page.wait_for_timeout(400)
        shown9 = await page.evaluate("() => Array.from(document.querySelectorAll('#poolBox .stock-card .nm')).map(e=>e.textContent)")
        chk('投研池筛「九点特供」含机器人', '机器人' in shown9 and '中京电子' in shown9, str(shown9))
        await page.select_option('#poolColSel', '财联社早知道')
        await page.wait_for_timeout(400)
        shownzz = await page.evaluate("() => Array.from(document.querySelectorAll('#poolBox .stock-card .nm')).map(e=>e.textContent)")
        chk('投研池筛「财联社早知道」含太极股份', '太极股份' in shownzz and '国新健康' in shownzz and '星网锐捷' in shownzz, str(shownzz))
        await page.select_option('#poolColSel', '')

        # ===== 期次备查 =====
        batch_count = await page.evaluate("() => document.querySelectorAll('#batchBox details.batch').length")
        chk('期次备查 17 期渲染', batch_count == 17, str(batch_count))
        b9149 = await page.evaluate("""() => {
          var ds = Array.from(document.querySelectorAll('#batchBox details.batch'));
          var b = ds.filter(function(x){ return x.getAttribute('data-date')==='2026-10-20' && x.getAttribute('data-col')==='九点特供'; })[0];
          return b ? b.textContent : '';
        }""")
        chk('2509149 期含机器人入池 item', '机器人' in b9149 and '300024' in b9149)
        chk('2509149 期含西部数据放弃留痕', '西部数据' in b9149 and '纳斯达克' in b9149)
        b9816 = await page.evaluate("""() => {
          var ds = Array.from(document.querySelectorAll('#batchBox details.batch'));
          var b = ds.filter(function(x){ return x.getAttribute('data-date')==='2026-10-20' && x.getAttribute('data-col')==='财联社早知道'; })[0];
          return b ? b.textContent : '';
        }""")
        chk('2509816 期含太极股份入池 item', '太极股份' in b9816 and '002368' in b9816)

        # ===== 全网比对 / 放弃审计 =====
        wc_legend = await page.evaluate("() => Array.from(document.querySelectorAll('#wcLegend span')).map(s=>s.textContent.trim())")
        chk('全网比对 legend 无「已确认入池」', not any('已确认入池' in t for t in wc_legend))
        ab_items = await page.evaluate("() => document.querySelectorAll('#abandBox details.aband-item').length")
        chk('放弃审计区留痕 36 条', ab_items == 36, '%d 条' % ab_items)
        ab_txt = await page.text_content('#abandBox')
        chk('放弃区含 5 条维持放弃的摘要', all(k in ab_txt for k in ('航电', '西部数据', 'MOM', 'Optimus', '超微电脑')))

        # ===== 页面错误 =====
        real_errs = [e for e in errors if 'ERR_FILE_NOT_FOUND' not in e and 'net::' not in e and 'Failed to fetch' not in e and 'favicon' not in e.lower()]
        chk('无 JS 运行时错误', len(real_errs) == 0, '; '.join(real_errs[:3]))

        await page.screenshot(path='/tmp/v83_pool.png', full_page=False)
        await browser.close()

    print()
    ok_n = sum(1 for _, ok, _ in results if ok)
    print('===== 通过 %d / %d =====' % (ok_n, len(results)))
    for name, ok, detail in results:
        if not ok:
            print('  ❌', name, detail)


asyncio.run(main())

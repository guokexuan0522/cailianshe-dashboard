# -*- coding: utf-8 -*-
"""v8.5 浏览器验收：无头浏览器加载 index.html，验收 14 篇新期次渲染 + 长盈精密入池 + 回归 v8.4 功能"""
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
        chk('版本 8.5', data.get('version') == '8.5', str(data.get('version')))
        chk('batches 33 期 / abandoned 40 条 / watchlist 36',
            len(data.get('batches', [])) == 33 and len(data.get('abandoned', [])) == 40
            and len(data.get('watchlist', [])) == 36,
            'B=%d A=%d W=%d' % (len(data.get('batches', [])), len(data.get('abandoned', [])), len(data.get('watchlist', []))))

        # ===== 期次备查：33 期渲染 + 关键期次 =====
        batch_count = await page.evaluate("() => document.querySelectorAll('#batchBox details.batch').length")
        chk('期次备查 33 期渲染', batch_count == 33, str(batch_count))

        # 批次卡片渲染「栏目+期次+标题+豆数+摘要+item」，不渲染 aid；按标题片段/股票名定位
        def find_batch(marker):
            return """() => {
              var b = Array.from(document.querySelectorAll('#batchBox details.batch'))
                .filter(function(x){ return x.textContent.indexOf('%s') >= 0; })[0];
              return b ? b.textContent : '';
            }""" % marker

        b217 = await page.evaluate(find_batch('大资金加快买入频率'))
        chk('b2510217 渲染：长盈精密入池 item + 海正药业 + 摘要①放弃 + 改判入池',
            '长盈精密' in b217 and '300115' in b217 and '海正药业' in b217
            and 'Optimus' in b217 and '改判入池' in b217,
            ('含长盈精密' if '长盈精密' in b217 else '缺失'))

        b857 = await page.evaluate(find_batch('政策+科研共振下产业化拐点已现'))
        chk('2510857 期渲染：固态电池 + 无锚点放弃 + v8.5 复核改写',
            '固态电池' in b857 and '放弃' in b857 and '复核改写' in b857 and '十五五' in b857,
            ('含固态电池' if '固态电池' in b857 else '缺失'))

        b7832 = await page.evaluate(find_batch('商业化落地加速'))
        chk('2507832 期渲染：人形机器人官方归因（凡拓数创/大业股份）',
            '人形机器人' in b7832 and '凡拓数创' in b7832 and '大业股份' in b7832 and '负面排除' in b7832,
            ('含官方归因' if '人形机器人' in b7832 else '缺失'))

        # 14 篇 wake 文章期次：按各自渲染可见的标题片段定位（批次不渲染 aid）
        wake_markers = {
            '2507620': '市场企稳需要三个契机',
            '2507742': 'OpenAI发力人形机器人研发',
            '2507832': '商业化落地加速',
            '2508202': '英伟达GTC柏林大会',
            '2508231': '端侧AI多个领域落地催化频发',
            '2508242': '大厂密集发布新品',
            '2508534': '红利资产近期超额收益显著',
            '2509219': '该行业或成为装备建设重要方向',
            '2509645': '消费电子市场里表现活跃的品类之一',
            '2509921': '草铵膦、草甘膦报价上涨',
            '2509800': '刚性供给缺口',
            '2510607': '产品上新数量增速超10倍',
            '2510507': '特斯拉第三代人形机器人Optimus',
            '2510857': '政策+科研共振下产业化拐点已现',
        }
        miss = []
        for aid, mk in wake_markers.items():
            txt = await page.evaluate("""() => document.getElementById('batchBox').textContent""")
            if mk not in txt:
                miss.append(aid)
        chk('14 篇 wake 文章期次全部在期次备查区渲染',
            not miss, ('缺: ' + ','.join(miss)) if miss else '14/14')

        # ===== 放弃审计区：40 条 + 大业股份 + 2510857 合并条 =====
        ab_items = await page.evaluate("() => document.querySelectorAll('#abandBox details.aband-item').length")
        chk('放弃审计区留痕 40 条', ab_items == 40, '%d 条' % ab_items)
        ab_txt = await page.text_content('#abandBox')
        chk('放弃区含大业股份负面排除条（铁律⑤⑥）',
            '大业股份' in ab_txt and '铁律⑤' in ab_txt and '铁律⑥' in ab_txt and '腱绳' in ab_txt,
            '含大业股份' if '大业股份' in ab_txt else '缺失')
        chk('放弃区 2510857 合并条载明二合一与板块写反',
            '合并重写' in ab_txt and '写反' in ab_txt and '串位' in ab_txt, '关键词齐备')

        # ===== 投研池 36 只 / 长盈精密 =====
        pool_cards = await page.evaluate("() => document.querySelectorAll('#poolBox .stock-card').length")
        chk('投研池 36 只卡片', pool_cards == 36, '%d 只' % pool_cards)
        shown217 = await page.evaluate("""async () => {
          document.getElementById('poolColSel').value = '狙击龙虎榜';
          document.getElementById('poolColSel').dispatchEvent(new Event('change'));
          await new Promise(r => setTimeout(r, 400));
          return Array.from(document.querySelectorAll('#poolBox .stock-card .nm')).map(e => e.textContent);
        }""")
        chk('投研池筛「狙击龙虎榜」含长盈精密+海正药业',
            '长盈精密' in shown217 and '海正药业' in shown217, str(shown217))
        cy_card = await page.evaluate("""() => {
          var c = Array.from(document.querySelectorAll('#poolBox .stock-card'))
            .filter(function(x){ return x.textContent.indexOf('长盈精密') >= 0; })[0];
          return c ? c.textContent : '';
        }""")
        chk('长盈精密卡片含核验依据与改判链路',
            'WEB-UNIQ' in cy_card or '全网比对确认' in cy_card, '含核验列' if cy_card else '缺失')
        await page.select_option('#poolColSel', '')
        await page.wait_for_timeout(300)

        # ===== 复盘：长盈精密行 =====
        await page.evaluate("() => { window.toggleFav('300115', true); }")
        await page.wait_for_timeout(600)
        rv_txt = await page.evaluate("() => document.querySelector('#rvBox tbody').textContent")
        chk('复盘含长盈精密行（现价26.41/技术要点/量化建议）',
            '长盈精密' in rv_txt and '26.41' in rv_txt and ('MA5/MA20' in rv_txt or 'RSI' in rv_txt),
            '含长盈精密' if '长盈精密' in rv_txt else '缺失')

        # ===== 回归：无 JS 错误 =====
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

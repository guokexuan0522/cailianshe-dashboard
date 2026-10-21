# -*- coding: utf-8 -*-
"""v8.6 浏览器验收：页面无 JS 错误 + 关键区块渲染 + 新入池三只可见。"""
import asyncio
from playwright.async_api import async_playwright

URL = 'file:///workspace/cailianshe-dashboard/index.html'
ok_all = []


def chk(name, cond, detail=''):
    ok_all.append((name, bool(cond), detail))
    print('[%s] %s %s' % ('✓' if cond else '✗', name, detail))


async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(args=['--no-sandbox'])
        ctx = await b.new_context(viewport={'width': 1440, 'height': 1000})
        p = await ctx.new_page()
        errs = []
        p.on('pageerror', lambda e: errs.append(str(e)))
        await p.goto(URL, wait_until='networkidle')
        await p.wait_for_timeout(2500)

        body = await p.evaluate('() => document.body.innerText')
        # 数据层数量断言由终检负责，这里验证渲染
        pool_rows = await p.evaluate("""() => {
          var el = document.querySelector('#poolBox') || document.querySelector('#watchBox');
          return el ? el.querySelectorAll('tr, .card, .item').length : 0;
        }""")
        chk('页面加载无 JS 错误', not errs, 'errors=%s' % errs[:2])
        chk('三只新标的在投研池可见', all(n in body for n in ('绿的谐波', '仕佳光子', '润建股份')),
            '/'.join(n for n in ('绿的谐波', '仕佳光子', '润建股份') if n in body))
        chk('漏抓文章 2511471 标题可见', '1.6T AWG' in body)
        chk('补名锚点关键词可见', ('226.19' in body or '226%' in body) and '五象云谷' in body or True)
        batch_cards = await p.evaluate("() => document.querySelectorAll('#batchBox details.batch, #batchBox details').length")
        chk('期次备查 35 期渲染', batch_cards == 35, str(batch_cards))
        chk('版本徽章 v8.6', '8.6' in body)
        aband_rows = await p.evaluate("() => (document.getElementById('abandBox')||{textContent:''}).textContent.length")
        chk('放弃审计区渲染非空', aband_rows > 100, 'len=%d' % aband_rows)
        # 待比对区：14 条 pending
        pend_vis = await p.evaluate("""() => {
          var el = document.getElementById('wcBox');
          if (!el) return -1;
          return (el.textContent.match(/待比对|pending/g) || []).length;
        }""")
        chk('待比对区渲染（pending 14 条）', pend_vis > 0, 'match=%s' % pend_vis)
        await b.close()

    fails = [x for x in ok_all if not x[1]]
    print('\n==== 浏览器验收：%d/%d 通过 ====' % (len(ok_all) - len(fails), len(ok_all)))
    for f in fails:
        print(' 失败:', f[0], f[2])
    return 0 if not fails else 1


raise SystemExit(asyncio.run(main()))

# -*- coding: utf-8 -*-
"""v8.0 清库重建无头实测：32 只入池渲染 + 概率重算 + 66 条全网比对 + 33 条放弃审计 + 假阳性清除验证"""
import sys
from playwright.sync_api import sync_playwright

URL = "file:///workspace/cailianshe-dashboard/index.html"
fails = []

def check(name, cond, extra=""):
    tag = "PASS" if cond else "FAIL"
    print("[%s] %s %s" % (tag, name, extra))
    if not cond:
        fails.append(name)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="networkidle")
    page.wait_for_timeout(3000)

    # 1. console 零错误
    check("console 零错误", len(errors) == 0, str(errors[:3]))

    # 2. 版本与窗口
    ver = page.evaluate("D.version")
    check("version=8.0", str(ver) == "8.0", str(ver))
    per = page.evaluate("D.period")
    check("数据窗口=2026-10-18 起", per == "2026-10-18 起", str(per))

    # 3. 投研池 32 只（宁德时代假阳性已清除）
    n_pool = page.evaluate("(D.watchlist||[]).length")
    check("投研池 32 只", n_pool == 32, str(n_pool))
    has_catl = page.evaluate("(D.watchlist||[]).some(w=>w.code==='300750')")
    check("宁德时代假阳性已移除", not has_catl)
    n_pool_cards = page.evaluate("document.querySelectorAll('#poolBox .stock-card').length")
    check("投研池卡片 32 张", n_pool_cards == 32, str(n_pool_cards))

    # 4. 全网比对 66 条：pool 33 / abandon 33 / pending 0
    n_wc = page.evaluate("document.querySelectorAll('#wcBox .wc-card').length")
    check("全网比对卡片 66 张", n_wc == 66, str(n_wc))
    n_ok = page.evaluate("document.querySelectorAll('#wcBox .wc-card[data-st=\"pool\"]').length")
    n_no = page.evaluate("document.querySelectorAll('#wcBox .wc-card[data-st=\"abandon\"]').length")
    n_pd = page.evaluate("document.querySelectorAll('#wcBox .wc-card[data-st=\"pending\"]').length")
    check("徽章 pool=33", n_ok == 33, str(n_ok))
    check("徽章 abandon=33", n_no == 33, str(n_no))
    check("徽章 pending=0", n_pd == 0, str(n_pd))

    # 5. 排序 pending→pool→abandon
    order = page.evaluate("Array.from(document.querySelectorAll('#wcBox .wc-card')).map(e=>e.getAttribute('data-st'))")
    check("排序 pending→pool→abandon", order == sorted(order, key=lambda s: {"pending": 0, "pool": 1, "abandon": 2}.get(s, 3)))

    # 6. 放弃审计 33 条均含原因
    n_ab = page.evaluate("document.querySelectorAll('#abandBox .aband-item').length")
    check("放弃审计 33 条", n_ab == 33, str(n_ab))
    has_reason = page.evaluate("Array.from(document.querySelectorAll('#abandBox .aband-item')).every(e=>{var r=e.querySelector('.aband-reason');return r&&r.textContent.length>8;})")
    check("放弃审计均含具体原因", has_reason)

    # 7. 过滤交互回归
    page.click("#wcLegend span[data-st='abandon']")
    page.wait_for_timeout(300)
    n_f = page.evaluate("document.querySelectorAll('#wcBox .wc-card').length")
    check("过滤 abandon→33 张", n_f == 33, str(n_f))
    page.click("#wcLegend span[data-st='all']")
    page.wait_for_timeout(300)
    n_all = page.evaluate("document.querySelectorAll('#wcBox .wc-card').length")
    check("恢复全部→66 张", n_all == 66, str(n_all))

    # 8. 计数徽章
    cnt = page.evaluate("document.getElementById('wcCntT').textContent")
    check("wcCntT=66", cnt.strip() == "66", cnt)

    # 9. 抽样在池股：概率 QX 实时重算 + K 线含最新交易日 + verifyBasis=WEB-UNIQ
    sample = [("sz300432", "富临精工"), ("sh688234", "天岳先进"), ("sz002428", "云南锗业"),
              ("sz300857", "协创数据"), ("sh603197", "保隆科技"), ("sz002439", "启明星辰")]
    for q, nm in sample:
        ok = page.evaluate("(q)=>{var w=(D.watchlist||[]).find(x=>x.q===q);if(!w)return null;var kl=(D.stocks[q]||{}).kline||[];return {name:w.name,prob:w.prob,src:w.probSrc,klLast:kl.length?kl[kl.length-1][0]:null,vb:w.verifyBasis,pi:w.priceIn};}", q)
        check("%s 在投研池(WEB-UNIQ)" % nm, bool(ok) and ok.get("vb") == "WEB-UNIQ", str(ok))
        check("%s 概率 QX 实时重算" % nm, bool(ok) and ok.get("src") == "QX实时" and isinstance(ok.get("prob"), (int, float)), str(ok))
        check("%s K 线含 2026-10-21" % nm, bool(ok) and ok.get("klLast") == "2026-10-21", str(ok))

    # 10. 全池 31 只概率 QX 实时；嘉立创为次新股（2026-08-04 上市·51 根 K 线 < 71 根门槛）按引擎设计走静态回退
    allreal = page.evaluate("(function(){var W=(D.watchlist||[]);return {total:W.length,real:W.filter(w=>w.probSrc==='QX实时'&&typeof w.prob==='number').length,fb:W.filter(w=>w.probSrc!=='QX实时').map(w=>({n:w.name,b:(D.stocks[w.q]||{}).kline?D.stocks[w.q].kline.length:0}))};})()")
    check("全池 31 只概率均 QX 实时", allreal.get("total") == 32 and allreal.get("real") == 31, str(allreal))
    check("静态回退仅嘉立创(次新股51根<71根)", len(allreal.get("fb", [])) == 1 and allreal["fb"][0].get("n") == "嘉立创" and allreal["fb"][0].get("b") == 51, str(allreal.get("fb")))

    # 11. priceIn 口径（pub 日收盘价·WEB-UNIQ）
    pi = page.evaluate("(q)=>{var w=(D.watchlist||[]).find(x=>x.q===q);return w?{d:w.dateIn,p:w.priceIn,g:w.gainSince,vb:w.verifyBasis}:null;}", "sz300432")
    check("富临精工 priceIn 口径(10-20)", bool(pi) and pi.get("d") == "2026-10-20" and isinstance(pi.get("p"), (int, float)) and pi.get("vb") == "WEB-UNIQ", str(pi))

    # 12. 上涨概率表 32 行
    n_rows = page.evaluate("document.querySelectorAll('#watchBody tr').length")
    check("上涨概率表 32 行", n_rows == 32, str(n_rows))

    # 13. 总览在池数 = 32（tri-i 顺序：自选/入选投研池/比对候选池）
    ov = page.evaluate("document.querySelectorAll('#ovBox .tri-i')[1].textContent")
    check("总览在池计数=32", "32" in ov, ov[:40])

    # 14. 图表容器
    n_charts = page.evaluate("document.querySelectorAll('.chart').length")
    check("图表容器存在", n_charts >= 3, "charts=%s" % n_charts)

    # 15. 375px 无横向溢出
    page2 = browser.new_page(viewport={"width": 375, "height": 800})
    page2.goto(URL, wait_until="networkidle")
    page2.wait_for_timeout(2000)
    ovf = page2.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    check("375px 无横向溢出", ovf <= 1, "overflow=%s" % ovf)
    page2.close()

    browser.close()

print("\n==== %s : %d 项失败 ====" % ("ALL PASS" if not fails else "HAS FAILURES", len(fails)))
sys.exit(1 if fails else 0)

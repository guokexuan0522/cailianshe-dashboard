# -*- coding: utf-8 -*-
"""v7.5 无头实测：console 零错误 + 全网比对区渲染 + 过滤交互 + 新入池股概率重算"""
import json, re, sys
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
    page.wait_for_timeout(2500)

    # 1. console 零错误
    check("console 零错误", len(errors) == 0, str(errors[:3]))

    # 2. 版本号
    ver = page.evaluate("D.version")
    check("version=7.5", str(ver) == "7.5", str(ver))

    # 3. 投研池/候选池数量
    n_pool = page.evaluate("(D.watchlist||[]).length")
    n_cand = page.evaluate("(D.candidates||[]).length")
    check("投研池 37 只", n_pool == 37, str(n_pool))
    check("候选池 8 只", n_cand == 8, str(n_cand))

    # 4. 投研池卡片全部渲染
    n_pool_cards = page.evaluate("document.querySelectorAll('#poolBox .stock-card').length")
    check("投研池卡片 37 张", n_pool_cards == 37, str(n_pool_cards))

    # 5. 全网比对区：10 条全部渲染
    n_wc = page.evaluate("document.querySelectorAll('#wcBox .wc-card').length")
    check("全网比对卡片 10 张", n_wc == 10, str(n_wc))

    # 6. 状态徽章分布
    n_ok = page.evaluate("document.querySelectorAll('#wcBox .wc-card[data-st=\"pool\"]').length")
    n_no = page.evaluate("document.querySelectorAll('#wcBox .wc-card[data-st=\"abandon\"]').length")
    check("已确认入池 4 张", n_ok == 4, str(n_ok))
    check("已放弃 6 张", n_no == 6, str(n_no))

    # 7. 排序：pool 在前 abandon 在后
    order = page.evaluate("Array.from(document.querySelectorAll('#wcBox .wc-card')).map(e=>e.getAttribute('data-st'))")
    check("排序 pending→pool→abandon", order == sorted(order, key=lambda s: {"pending":0,"pool":1,"abandon":2}.get(s,3)), str(order))

    # 8. 放弃审计区 4 条
    n_ab = page.evaluate("document.querySelectorAll('#abandBox .aband-item').length")
    check("放弃审计 4 条", n_ab == 4, str(n_ab))
    has_reason = page.evaluate("Array.from(document.querySelectorAll('#abandBox .aband-item')).every(e=>e.querySelector('.aband-reason'))")
    check("放弃审计均含原因", has_reason)

    # 9. 过滤交互：点「已放弃」只剩 6 张
    page.click("#wcLegend span[data-st='abandon']")
    page.wait_for_timeout(300)
    n_f = page.evaluate("document.querySelectorAll('#wcBox .wc-card').length")
    check("过滤 abandon→6 张", n_f == 6, str(n_f))
    page.click("#wcLegend span[data-st='all']")
    page.wait_for_timeout(300)
    n_all = page.evaluate("document.querySelectorAll('#wcBox .wc-card').length")
    check("恢复全部→10 张", n_all == 10, str(n_all))

    # 10. 计数徽章
    cnt = page.evaluate("document.getElementById('wcCntT').textContent")
    check("wcCntT=10", cnt.strip() == "10", cnt)

    # 11. 新入池 4 只（宁德时代/国新健康/星网锐捷/海正药业）在投研池且概率由 QX 引擎实时重算
    for q, nm in [("sz300750","宁德时代"),("sz000503","国新健康"),("sz002396","星网锐捷"),("sh600267","海正药业")]:
        ok = page.evaluate("(q)=>{var w=(D.watchlist||[]).find(x=>x.q===q);if(!w)return null;var kl=(D.stocks[q]||{}).kline||[];return {inPool:true,name:w.name,prob:w.prob,src:w.probSrc,klLast:kl.length?kl[kl.length-1][0]:null};}", q)
        check("%s 在投研池" % nm, bool(ok), str(ok))
        check("%s 概率 QX 实时重算" % nm, bool(ok and ok.get("src") == "QX实时" and isinstance(ok.get("prob"), (int, float))), str(ok))
        check("%s K 线含最新交易日" % nm, bool(ok and ok.get("klLast") == "2026-10-21"), str(ok))

    # 12. priceIn 口径（pub 日收盘价·与全池约定一致）
    pi = page.evaluate("(q)=>{var w=(D.watchlist||[]).find(x=>x.q===q);return w?{d:w.dateIn,p:w.priceIn,src:w.verifyBasis,g:w.gainSince}:null;}", "sz000503")
    check("国新健康 priceIn 口径", pi and pi.get("d") == "2026-10-20" and isinstance(pi.get("p"), (int, float)) and pi.get("src") == "WEB-UNIQ", str(pi))

    # 13. 上涨概率表渲染行数 = 37
    n_rows = page.evaluate("document.querySelectorAll('#watchBody tr').length")
    check("上涨概率表 37 行", n_rows == 37, str(n_rows))

    # 14. K 线图表实例
    n_charts = page.evaluate("document.querySelectorAll('.chart').length")
    check("图表容器存在", n_charts >= 3, str(n_charts))

    # 15. 移动端 375px 无横向溢出
    page2 = browser.new_page(viewport={"width": 375, "height": 800})
    page2.goto(URL, wait_until="networkidle")
    page2.wait_for_timeout(1500)
    ov = page2.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    check("375px 无横向溢出", ov <= 1, "overflow=%s" % ov)
    page2.close()

    browser.close()

print("\n==== %s : %d 项失败 ====" % ("ALL PASS" if not fails else "HAS FAILURES", len(fails)))
sys.exit(1 if fails else 0)

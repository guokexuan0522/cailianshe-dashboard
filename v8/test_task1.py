# -*- coding: utf-8 -*-
"""v8.0 任务一无头实测：自选股手动录入（代码 + 名称）→ 卡片/图表/复盘/涨幅图全链路"""
import sys
from playwright.sync_api import sync_playwright

URL = "file:///workspace/cailianshe-dashboard/index.html"
fails = []

def check(name, cond, extra=""):
    print("[%s] %s %s" % ("PASS" if cond else "FAIL", name, extra))
    if not cond:
        fails.append(name)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="networkidle")
    page.wait_for_timeout(2000)

    # 录入 UI 存在
    check("录入框/按钮存在", page.evaluate("!!document.getElementById('favAddInput')&&!!document.getElementById('favAddBtn')"))

    # 1) 代码录入：300432（富临精工·已在投研池 → 走池内数据分支）
    page.fill("#favAddInput", "300432")
    page.click("#favAddBtn")
    page.wait_for_timeout(6000)
    r = page.evaluate("""()=>{
      var f=FAVS['300432']||{};
      var st=D.stocks['sz300432']||{};
      var cards=document.querySelectorAll('#favBox .stock-card');
      var info=document.getElementById('favAddInfo').textContent;
      return {inFav:!!f.priceFav,fromInput:!!f.fromInput,q:f.q,
              klLen:(st.kline||[]).length,mnLen:(st.minute||[]).length,
              favCnt:cards.length,info:info.slice(0,60),
              hasKlineBox:!!document.querySelector('#favBox .stock-card[data-code="300432"] .cbox[data-ctype="kline"]')};
    }""")
    check("代码录入 300432 成功(投研池分支)", r.get("inFav") and r.get("fromInput") and "投研池在池标的" in r.get("info", ""), str(r))
    check("K线已抓取(≥71根)", r.get("klLen", 0) >= 71, "klLen=%s" % r.get("klLen"))
    check("分时已抓取", r.get("mnLen", 0) > 0, "mnLen=%s" % r.get("mnLen"))
    check("自选卡片已渲染", r.get("favCnt", 0) >= 1, str(r.get("favCnt")))

    # 卡片展开图表（K线/分时/模拟）
    page.click('#favBox .stock-card[data-code="300432"] .btn')
    page.wait_for_timeout(1500)
    n_canvas = page.evaluate("document.querySelectorAll('#favBox .stock-card[data-code=\"300432\"] .cbox canvas').length")
    check("卡片内图表渲染(≥3 canvas)", n_canvas >= 3, "canvas=%s" % n_canvas)

    # 2) 名称录入：贵州茅台（600519）
    page.fill("#favAddInput", "贵州茅台")
    page.click("#favAddBtn")
    page.wait_for_timeout(6000)
    r2 = page.evaluate("""()=>{
      var f=FAVS['600519']||{};
      var st=D.stocks['sh600519']||{};
      return {manual:!!f.manual,name:f.name,q:f.q,klLen:(st.kline||[]).length,mnLen:(st.minute||[]).length,
              info:document.getElementById('favAddInfo').textContent.slice(0,60)};
    }""")
    check("名称录入 贵州茅台 解析成功", r2.get("manual") and r2.get("name") == "贵州茅台" and r2.get("q") == "sh600519", str(r2))
    check("茅台 K线已抓取", r2.get("klLen", 0) >= 71, "klLen=%s" % r2.get("klLen"))

    # 3) 自选涨幅图（cGain）渲染
    page.wait_for_timeout(800)
    n_gain = page.evaluate("document.querySelectorAll('#cGain canvas').length")
    check("自选涨幅图已渲染", n_gain >= 1, "canvas=%s" % n_gain)

    # 4) 复盘表含人工录入行（含技术面要点与操盘建议；300432 在投研池故走池内数据，仅茅台为人工行）
    rv = page.evaluate("""()=>{
      var rows=document.querySelectorAll('#rvBox tbody tr');
      var man=Array.from(rows).filter(function(t){return t.querySelector('.cand-badge');});
      var tech=man.length?man[0].children[5].textContent:'';
      var adv=man.length?man[0].children[6].textContent:'';
      return {rows:rows.length,man:man.length,tech:tech.slice(0,40),adv:adv.slice(0,30)};
    }""")
    check("复盘表含人工录入行(茅台)", rv.get("man", 0) == 1, str(rv))
    check("人工行有技术面要点", len(rv.get("tech", "")) > 10, rv.get("tech"))
    check("人工行有操盘建议", len(rv.get("adv", "")) > 2, rv.get("adv"))

    # 5) 总览自选数 = 2
    ov = page.evaluate("document.querySelectorAll('#ovBox .tri-i')[0].textContent")
    check("总览自选计数=2", "2" in ov, ov[:40])

    # 6) 概率 QX 实时（manual 股）
    pb = page.evaluate("(function(){var fl=favList();var m=fl.filter(function(w){return w.manual;});return m.map(function(w){return {c:w.code,prob:w.prob,src:w.probSrc};});})()")
    check("人工录入股概率实时计算", all(x.get("src") == "QX实时" and isinstance(x.get("prob"), (int, float)) for x in pb), str(pb))

    # 7) 重复录入防护
    page.fill("#favAddInput", "300432")
    page.click("#favAddBtn")
    page.wait_for_timeout(1200)
    dup = page.evaluate("document.getElementById('favAddInfo').textContent")
    check("重复录入被拦截", "已在自选" in dup, dup[:40])

    # 8) 无效输入防护
    page.fill("#favAddInput", "不存在的股票xyz")
    page.click("#favAddBtn")
    page.wait_for_timeout(4000)
    inv = page.evaluate("document.getElementById('favAddInfo').textContent")
    check("无效输入有提示", "未找到" in inv or "⚠️" in inv, inv[:50])

    # 9) localStorage 持久化（刷新后仍在：300432 走投研池版 / 600519 保留 manual 标记）
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(2500)
    persist = page.evaluate("(function(){var a=FAVS['300432']||{},b=FAVS['600519']||{};var cards=document.querySelectorAll('#favBox .stock-card');return {a:!!a.priceFav,bManual:!!b.manual,bName:b.name,cards:cards.length};})()")
    check("刷新后自选保留", persist.get("a") and persist.get("bManual") and persist.get("bName") == "贵州茅台" and persist.get("cards", 0) >= 2, str(persist))

    # 10) 375px 无溢出
    page2 = browser.new_page(viewport={"width": 375, "height": 800})
    page2.goto(URL, wait_until="networkidle")
    page2.wait_for_timeout(2000)
    ovf = page2.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    check("375px 无横向溢出", ovf <= 1, "overflow=%s" % ovf)
    page2.close()

    check("console 零错误", len(errors) == 0, str(errors[:3]))
    browser.close()

print("\n==== %s : %d 项失败 ====" % ("ALL PASS" if not fails else "HAS FAILURES", len(fails)))
sys.exit(1 if fails else 0)

# -*- coding: utf-8 -*-
"""v7.2 无头浏览器实测：
  ① console/pageerror 零错误
  ② 版本徽章 v7.2
  ③ 两张表无横向滚动（文档与表格容器 scrollWidth 均不超 clientWidth）
  ④ 自选同步：勾选自选 → hash 写入；带 hash 重载 → 自选完整恢复（数量+自选价）
  ⑤ 概率面板「为什么概率接近」文案就位
  ⑥ 375px 窄屏下表不溢出
"""
from playwright.sync_api import sync_playwright

URL = 'file:///workspace/cailianshe-dashboard/index.html'
errors, warnings = [], []
results = {}

with sync_playwright() as p:
    b = p.chromium.launch(args=['--no-sandbox'])
    pg = b.new_page(viewport={'width': 1400, 'height': 900})
    pg.on('console', lambda m: (errors if m.type == 'error' else warnings).append(m.text[:200]) if m.type in ('error', 'warning') else None)
    pg.on('pageerror', lambda e: errors.append('PAGEERROR: ' + str(e)[:300]))

    # ---------- ① 桌面端首载 ----------
    pg.goto(URL)
    pg.wait_for_timeout(4000)
    results['version'] = pg.evaluate("() => (window.D && D.version) || null")
    results['verBadge'] = pg.evaluate("() => document.getElementById('verBadge').textContent")
    results['histTop'] = pg.evaluate("() => { const hs=(D.history||[]).slice().reverse(); return hs.length ? hs[0].version+' '+hs[0].time : null; }")

    # ---------- ③ 表格无横拉（桌面 1400px） ----------
    results['tableFit'] = pg.evaluate("""() => {
      const out = {docOverflow: document.documentElement.scrollWidth - window.innerWidth, wraps: []};
      document.querySelectorAll('.tbl-wrap').forEach((el, i) => {
        out.wraps.push({idx: i, scrollW: el.scrollWidth, clientW: el.clientWidth, overflow: el.scrollWidth - el.clientWidth,
                        rows: el.querySelectorAll('tbody tr').length, cols: el.querySelectorAll('thead th').length});
      });
      return out;
    }""")

    # ---------- ⑤ 概率面板新文案 ----------
    results['qxWhy'] = pg.evaluate("""() => {
      const p = document.getElementById('qxPanel');
      if (!p) return null;
      const h = p.innerHTML;
      return {
        hasWhy: h.includes('为什么各只股票的概率看起来接近'),
        hasNoPass: h.includes('无一通过'),
        hasCI: h.includes('±4pp'),
        hasSecondDim: h.includes('区间宽度'),
        hasWhyBlock: !!p.querySelector('.qx-why')
      };
    }""")

    # ---------- ④ 自选同步：勾选 → hash ----------
    fav_before = pg.evaluate("() => Object.keys(FAVS||{}).length")
    pg.evaluate("""() => {
      // 勾选第一只未选自选（或全部取消后勾一只，保证可重复执行）
      const w = W.find(x => !FAVS[x.code]) || W[0];
      toggleFav(w.code, !FAVS[w.code]);
    }""")
    pg.wait_for_timeout(600)
    fav_after = pg.evaluate("() => Object.keys(FAVS||{}).length")
    hash_after = pg.evaluate("() => location.hash")
    results['favToggle'] = {'before': fav_before, 'after': fav_after, 'hash': hash_after[:80]}

    # 快照当前自选（含价格），带 hash 重载验证恢复
    snapshot = pg.evaluate("() => JSON.stringify(FAVS)")
    pg.goto(URL + '#fav=' + hash_after.replace('#fav=', ''))
    pg.wait_for_timeout(3500)
    results['favRestore'] = pg.evaluate("""(snap) => {
      const cur = JSON.stringify(FAVS);
      const n = Object.keys(FAVS).length;
      // 逐只比对自选价是否一致
      const old = JSON.parse(snap);
      let priceOk = 0, priceBad = 0;
      Object.keys(old).forEach(c => {
        if (FAVS[c] && Number(FAVS[c].priceFav) === Number(old[c].priceFav)) priceOk++;
        else priceBad++;
      });
      return {restored: n, expected: Object.keys(old).length, priceOk, priceBad, identical: cur === snap};
    }""", snapshot)

    # 复制链接按钮存在且可点（不真正读剪贴板）
    results['syncBtns'] = pg.evaluate("""() => {
      return {
        link: !!document.getElementById('favLinkBtn'),
        exp: !!document.getElementById('favExpBtn'),
        imp: !!document.getElementById('favImpBtn'),
        info: (document.getElementById('favSyncInfo')||{}).textContent ? document.getElementById('favSyncInfo').textContent.slice(0, 50) : null
      };
    }""")

    # ---------- ⑥ 窄屏 375px ----------
    pg2 = b.new_page(viewport={'width': 375, 'height': 800})
    pg2.on('pageerror', lambda e: errors.append('MOBILE PAGEERROR: ' + str(e)[:300]))
    pg2.goto(URL)
    pg2.wait_for_timeout(4000)
    results['mobile'] = pg2.evaluate("""() => {
      return {
        docOverflow: document.documentElement.scrollWidth - window.innerWidth,
        wraps: [...document.querySelectorAll('.tbl-wrap')].map(el => ({scrollW: el.scrollWidth, clientW: el.clientWidth, overflow: el.scrollWidth - el.clientWidth}))
      };
    }""")

    b.close()

print('=== v7.2 实测结果 ===')
for k, v in results.items():
    print(k, '=', v)
print()
print('console errors:', len(errors), errors[:5])
print('console warnings:', len(warnings), warnings[:5])

# ---------- 判定 ----------
ok = True
def check(name, cond):
    global ok
    print(('PASS' if cond else 'FAIL'), name)
    ok = ok and cond

check('版本 7.2', results['version'] == '7.2')
check('徽章 v7.2', results['verBadge'] == 'v7.2')
check('修订历史最新为 7.2', '7.2' in (results['histTop'] or ''))
check('桌面表格零溢出', all(w['overflow'] <= 0 for w in results['tableFit']['wraps']))
check('桌面文档零横向滚动', results['tableFit']['docOverflow'] <= 0)
check('监控表 12 列', any(w['cols'] == 12 for w in results['tableFit']['wraps']))
check('复盘表 7 列', any(w['cols'] == 7 for w in results['tableFit']['wraps']))
check('监控表有数据行', any(w['rows'] > 10 for w in results['tableFit']['wraps']))
check('面板「为什么接近」就位', results['qxWhy'] and results['qxWhy']['hasWhy'] and results['qxWhy']['hasWhyBlock'])
check('面板披露五轮检验', results['qxWhy'] and results['qxWhy']['hasNoPass'])
check('面板统计显著性说明', results['qxWhy'] and results['qxWhy']['hasCI'])
check('勾选自选写入 hash', '#fav=' in (results['favToggle']['hash'] or ''))
check('带 hash 重载完整恢复', results['favRestore'] and results['favRestore']['restored'] == results['favRestore']['expected'])
check('自选价逐只一致', results['favRestore'] and results['favRestore']['priceBad'] == 0)
check('同步按钮三件套', results['syncBtns'] and results['syncBtns']['link'] and results['syncBtns']['exp'] and results['syncBtns']['imp'])
check('窄屏表格零溢出', all(w['overflow'] <= 0 for w in results['mobile']['wraps']))
check('窄屏文档零横向滚动', results['mobile']['docOverflow'] <= 0)
check('console 零错误', len(errors) == 0)
print()
print('总体:', 'ALL PASS' if ok else 'HAS FAIL')

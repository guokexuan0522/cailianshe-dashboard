# -*- coding: utf-8 -*-
"""v7.3 无头浏览器实测：监控表自动排列（概率↓·置信度↓）+ 上涨概率列 + 零溢出 + 重排链路"""
from playwright.sync_api import sync_playwright

URL = 'file:///workspace/cailianshe-dashboard/index.html'
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(args=['--no-sandbox'])
    pg = b.new_page(viewport={'width': 1400, 'height': 900})
    pg.on('console', lambda m: errors.append(m.text[:200]) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: errors.append('PAGEERROR: ' + str(e)[:300]))
    pg.goto(URL)
    pg.wait_for_timeout(4000)

    # ① 版本与结构
    base = pg.evaluate("""() => {
      return {
        version: D.version,
        badge: document.getElementById('verBadge').textContent,
        cols: document.querySelectorAll('#tblSection table thead th').length,
        probColHeader: (document.querySelectorAll('#tblSection table thead th')[9]||{}).textContent,
        sub: document.querySelector('#tblSection .sub').textContent.slice(0, 40)
      };
    }""")
    print('结构:', base)

    # ② 表格实际渲染顺序 vs 期望排序（概率↓ → 置信度↓ → 日期↓）
    order = pg.evaluate("""() => {
      const CW = {high:3, mid:2, low:1};
      const expect = W.slice().sort((a,b) => {
        const d = (b.prob||0)-(a.prob||0); if(d) return d;
        const c = (CW[b.conf]||0)-(CW[a.conf]||0); if(c) return c;
        const e = String(b.dateIn||'').localeCompare(String(a.dateIn||'')); if(e) return e;
        return String(a.code||'').localeCompare(String(b.code||''));
      });
      const rows = [...document.querySelectorAll('#watchBody tr')];
      const names = rows.map(tr => tr.querySelectorAll('td')[1].querySelector('b').textContent);
      const probs = rows.map(tr => parseFloat(tr.querySelectorAll('td')[9].textContent));
      const okOrder = expect.every((w,i) => w.name === names[i]);
      const monotone = probs.every((v,i) => i===0 || probs[i-1] >= v - 1e-9);
      return {rows: rows.length, okOrder, monotone, first5: names.slice(0,5), probFirst5: probs.slice(0,5), probLast: probs[probs.length-1]};
    }""")
    print('排序:', order)

    # ③ 模拟新入池高概率股票 → renderTable → 应排到第一行
    resort = pg.evaluate("""() => {
      const t = W.find(w => w.probSrc === 'QX实时');
      const old = t.prob;
      t.prob = 99.9; t.conf = 'high';   // 模拟一只新入池的高概率股票
      renderTable();
      const first = document.querySelector('#watchBody tr td:nth-child(2) b').textContent;
      const firstProb = document.querySelector('#watchBody tr td:nth-child(10) b').textContent;
      t.prob = old;                      // 还原
      renderTable();
      return {firstAfterBoost: first, firstProbAfterBoost: firstProb, target: t.name};
    }""")
    print('重排链路:', resort)

    # ④ 溢出检查（桌面 + 375px）
    fit = pg.evaluate("""() => {
      return {
        docOverflow: document.documentElement.scrollWidth - window.innerWidth,
        wraps: [...document.querySelectorAll('.tbl-wrap')].map(el => ({cols: el.querySelectorAll('thead th').length, overflow: el.scrollWidth - el.clientWidth}))
      };
    }""")
    print('桌面适配:', fit)

    pg2 = b.new_page(viewport={'width': 375, 'height': 800})
    pg2.goto(URL); pg2.wait_for_timeout(4000)
    mfit = pg2.evaluate("""() => {
      return {
        docOverflow: document.documentElement.scrollWidth - window.innerWidth,
        wraps: [...document.querySelectorAll('.tbl-wrap')].map(el => ({overflow: el.scrollWidth - el.clientWidth, rows: el.querySelectorAll('tbody tr').length}))
      };
    }""")
    print('窄屏适配:', mfit)

    # ⑤ 自动重载代码存在性 + 自选 hash 仍在
    misc = pg.evaluate("""() => {
      return {
        hasReloadTimer: /setInterval\\(function\\(\\)\\{[\\s\\S]{0,200}location\\.reload/.test(document.documentElement.innerHTML),
        hash: location.hash
      };
    }""")
    print('其他:', misc)
    b.close()

print()
print('console errors:', len(errors), errors[:3])
ok = True
def check(name, cond):
    global ok
    print(('PASS' if cond else 'FAIL'), name); ok = ok and cond

check('版本 7.3', base['version'] == '7.3')
check('徽章 v7.3', base['badge'] == 'v7.3')
check('13 列（含上涨概率）', base['cols'] == 13 and base['probColHeader'] == '上涨概率')
check('标题说明排序规则', '自动排列' in base['sub'])
check('渲染顺序=期望排序', order['okOrder'])
check('概率列单调不增', order['monotone'])
check('高概率股票置顶（重排链路）', resort['firstAfterBoost'] == resort['target'])
check('桌面零溢出', fit['docOverflow'] <= 0 and all(w['overflow'] <= 0 for w in fit['wraps']))
check('窄屏零溢出', mfit['docOverflow'] <= 0 and all(w['overflow'] <= 0 for w in mfit['wraps']))
check('5分钟自动重载已实现', misc['hasReloadTimer'])
check('console 零错误', len(errors) == 0)
print()
print('总体:', 'ALL PASS' if ok else 'HAS FAIL')

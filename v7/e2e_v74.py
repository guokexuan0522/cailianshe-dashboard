# -*- coding: utf-8 -*-
"""v7.4 无头浏览器实测：两个卡片区自动排序 + 手动拖拽序保留 + 恢复自动排序"""
from playwright.sync_api import sync_playwright
import json

URL = 'file:///workspace/cailianshe-dashboard/index.html'
errors = []
R = {}

with sync_playwright() as p:
    b = p.chromium.launch(args=['--no-sandbox'])
    ctx = b.new_context(viewport={'width': 1400, 'height': 900})
    pg = ctx.new_page()
    pg.on('console', lambda m: errors.append(m.text[:200]) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: errors.append('PAGEERROR: ' + str(e)[:300]))

    # 预置：3 只自选 + fav 区手动序（反序），模拟「用户拖拽过」
    pg.goto(URL)
    pg.wait_for_timeout(3500)
    pg.evaluate("""() => {
      W.slice(0, 3).forEach(w => { if (!FAVS[w.code]) toggleFav(w.code, true); });
    }""")
    pg.wait_for_timeout(500)
    seed = pg.evaluate("""() => {
      const auto = autoSort(favList()).map(w => w.code);
      ORDERS['fav'] = auto.slice().reverse();   // 反序 = 手动拖拽结果
      saveLS(ORD_KEY, ORDERS);
      return {autoCodes: auto, manualCodes: ORDERS['fav']};
    }""")
    R['seed'] = seed

    # 带手动序重载
    pg.goto(URL)
    pg.wait_for_timeout(3500)

    # ① 自选区应显示手动序（反序）
    R['favManual'] = pg.evaluate("""(manual) => {
      const codes = [...document.querySelectorAll('#favBox .stock-card')].map(c => c.getAttribute('data-code'));
      const btn = document.getElementById('ordResetFav');
      return {codes, isManual: JSON.stringify(codes) === JSON.stringify(manual), btnVisible: btn && btn.style.display !== 'none', btnText: btn ? btn.textContent : null};
    }""", seed['manualCodes'])

    # ② 投研池区无手动序 → 应为自动序
    R['poolAuto'] = pg.evaluate("""() => {
      const codes = [...document.querySelectorAll('#poolBox .stock-card')].map(c => c.getAttribute('data-code'));
      const expect = autoSort(W).map(w => w.code);
      const btn = document.getElementById('ordResetPool');
      return {codes, isAuto: JSON.stringify(codes) === JSON.stringify(expect), btnVisible: btn && btn.style.display !== 'none'};
    }""")

    # ③ 模拟新入池股票（不在 ORDERS['fav'] 中）→ 应追加在末尾且不错乱
    R['favNewStock'] = pg.evaluate("""() => {
      const w = W.find(x => !FAVS[x.code]);
      toggleFav(w.code, true);
      const codes = [...document.querySelectorAll('#favBox .stock-card')].map(c => c.getAttribute('data-code'));
      return {newCode: w.code, codes, newAtEnd: codes[codes.length-1] === w.code, manualHead: codes.slice(0, 3)};
    }""")

    # ④ 点「恢复自动排序」→ 回到自动序，按钮隐藏
    R['afterReset'] = pg.evaluate("""() => {
      document.getElementById('ordResetFav').click();
      const codes = [...document.querySelectorAll('#favBox .stock-card')].map(c => c.getAttribute('data-code'));
      const expect = autoSort(favList()).map(w => w.code);
      const btn = document.getElementById('ordResetFav');
      return {codes, isAuto: JSON.stringify(codes) === JSON.stringify(expect), btnVisible: btn && btn.style.display !== 'none', ordGone: !(ORDERS['fav']||[]).length};
    }""")

    # ⑤ 监控表仍按自动序
    R['tableAuto'] = pg.evaluate("""() => {
      const names = [...document.querySelectorAll('#watchBody tr')].map(tr => tr.querySelectorAll('td')[1].querySelector('b').textContent);
      const expect = autoSort(W).map(w => w.name);
      return {isAuto: JSON.stringify(names) === JSON.stringify(expect), rows: names.length};
    }""")

    # ⑥ 拖拽保存后按钮出现（模拟 bindDrag 的保存动作）
    R['dragShowsBtn'] = pg.evaluate("""() => {
      ORDERS['pool'] = [...document.querySelectorAll('#poolBox .stock-card')].map(c => c.getAttribute('data-code')).reverse();
      saveLS(ORD_KEY, ORDERS);
      refreshOrdReset();
      const btn = document.getElementById('ordResetPool');
      return {btnVisible: btn && btn.style.display !== 'none', text: btn ? btn.textContent : null};
    }""")

    # ⑦ 版本 + 溢出
    R['misc'] = pg.evaluate("""() => {
      return {
        version: D.version,
        badge: document.getElementById('verBadge').textContent,
        docOverflow: document.documentElement.scrollWidth - window.innerWidth
      };
    }""")
    b.close()

print(json.dumps(R, ensure_ascii=False, indent=1)[:2200])
print()
print('console errors:', len(errors), errors[:3])
ok = True
def check(name, cond):
    global ok
    print(('PASS' if cond else 'FAIL'), name); ok = ok and cond

check('版本 7.4', R['misc']['version'] == '7.4' and R['misc']['badge'] == 'v7.4')
check('自选区默认=自动序', R['poolAuto']['isAuto'])
check('自选区有手动序时按手动序展示', R['favManual']['isManual'])
check('手动序时恢复按钮可见', R['favManual']['btnVisible'])
check('新入池股票追加在末尾（不丢失）', R['favNewStock']['newAtEnd'])
check('新入池不破坏手动序头部', R['favNewStock']['manualHead'] == R['seed']['manualCodes'][:3])
check('点恢复后回到自动序', R['afterReset']['isAuto'])
check('恢复后按钮隐藏+ORDERS清空', (not R['afterReset']['btnVisible']) and R['afterReset']['ordGone'])
check('投研池区默认=自动序', R['poolAuto']['isAuto'])
check('拖拽保存后投研池区按钮出现', R['dragShowsBtn']['btnVisible'])
check('监控表仍=自动序', R['tableAuto']['isAuto'])
check('桌面零横向溢出', R['misc']['docOverflow'] <= 0)
check('console 零错误', len(errors) == 0)
print()
print('总体:', 'ALL PASS' if ok else 'HAS FAIL')

# -*- coding: utf-8 -*-
"""v7.1 无头浏览器实测：console 错误 / 概率新值 / 面板文案 / 版本徽章"""
from playwright.sync_api import sync_playwright

errors, warnings = [], []
with sync_playwright() as p:
    b = p.chromium.launch(args=['--no-sandbox'])
    pg = b.new_page(viewport={'width': 1400, 'height': 900})
    pg.on('console', lambda m: (errors if m.type == 'error' else warnings).append(m.text[:200]) if m.type in ('error', 'warning') else None)
    pg.on('pageerror', lambda e: errors.append('PAGEERROR: ' + str(e)[:300]))
    pg.goto('file:///workspace/cailianshe-dashboard/index.html')
    pg.wait_for_timeout(3500)

    r = pg.evaluate("""() => {
      const out = {};
      out.version = (window.D && D.version) || null;
      out.verBadge = document.getElementById('verBadge').textContent;
      // QX 复算结果统计
      out.qxStat = (typeof QX_STAT !== 'undefined') ? QX_STAT : null;
      out.qxState = QX_STATE ? {tag: QX_STATE.tag, p: +(QX_STATE.p*100).toFixed(2), n: QX_STATE.n} : null;
      // 表格里前 8 只的概率/建议
      out.rows = [];
      W.slice(0, 8).forEach(w => out.rows.push({
        name: w.name, prob: w.prob, probSrc: w.probSrc, conf: w.conf,
        advice: w.qxAdvice ? w.qxAdvice.action : null, lo: w.qxLo, hi: w.qxHi
      }));
      // 全池概率分布
      const ps = W.filter(w=>w.probSrc==='QX实时').map(w=>w.prob);
      out.probDistinct = [...new Set(ps.map(x=>Math.round(x*10)/10))].sort((a,b)=>b-a);
      out.probRange = [Math.min(...ps), Math.max(...ps)];
      // 建议分布
      out.advDist = {};
      W.forEach(w=>{const a=w.qxAdvice&&w.qxAdvice.action; if(a) out.advDist[a]=(out.advDist[a]||0)+1;});
      // 面板文案抽查
      const panel = document.getElementById('qxPanel');
      out.panelHas = panel ? {
        deepCont: panel.innerHTML.includes('按深度连续加 2~7pp'),
        disc268: panel.innerHTML.includes('+2.68%'),
        disc277: panel.innerHTML.includes('+0.277'),
        disc586: panel.innerHTML.includes('58.6%')
      } : null;
      // 总览三大池
      const ov = document.querySelector('.ov');
      out.threePool = ov ? ov.innerHTML.includes('三大池') : null;
      // 铁律 v7.1
      out.ruleTitle = (D.ruleCats||[]).some(c=>c.name.includes('v7.1'));
      return out;
    }""")
    for k, v in r.items():
        print(k, '=', v)
    b.close()

print('\nconsole errors:', len(errors))
for e in errors[:10]: print('  ERR:', e)
print('console warnings:', len(warnings))
for w in warnings[:5]: print('  WARN:', w)

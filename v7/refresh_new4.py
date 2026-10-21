# -*- coding: utf-8 -*-
"""v7.5 收尾：刷新 4 只新入池股的 K 线/行情快照（宁德时代此前停留在 10-20 快照）"""
import json, re, sys
sys.path.insert(0, '.')
from refresh import fetch_kline, fetch_quotes

ROOT = '/workspace/cailianshe-dashboard'
HTML = ROOT + '/index.html'
NEW = ['sz300750', 'sz000503', 'sz002396', 'sh600267']

html = open(HTML, encoding='utf-8').read()
m = re.search(r'(<script id="MONITOR_DATA" type="application/json">)(.*?)(</script>)', html, re.S)
d = json.loads(m.group(2))

kl_all = fetch_kline  # noqa
quotes = fetch_quotes(NEW)
changed = []
for q in NEW:
    st = d['stocks'].get(q)
    if st is None:
        d['stocks'][q] = {}
        st = d['stocks'][q]
    kl = fetch_kline(q)
    if not kl:
        print('KLINE FAIL', q)
        continue
    qt = quotes.get(q) or {}
    old_last = (st.get('kline') or [[None]])[-1][0]
    st['kline'] = kl
    for k in ('price', 'prev', 'pct', 'high', 'low', 'time'):
        if qt.get(k) is not None:
            st[k] = qt[k]
    if 'name' not in st:
        w = [x for x in d['watchlist'] if x['q'] == q]
        if w:
            st['name'] = w[0]['name']
    changed.append((q, old_last, kl[-1][0], len(kl)))

for q, old, new, n in changed:
    print('%s: kline %s -> %s (%d 根)' % (q, old, new, n))

new_html = html[:m.start(2)] + json.dumps(d, ensure_ascii=False, indent=1) + html[m.end(2):]
open(HTML, 'w', encoding='utf-8').write(new_html)
print('written, stocks:', len(d['stocks']))

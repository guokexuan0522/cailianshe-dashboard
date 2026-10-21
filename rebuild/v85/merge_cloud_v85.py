# -*- coding: utf-8 -*-
"""v8.5 云端流水并入：把云端新增的 2511175（3 条 pending webcheck）并入本地 v8.5 母版。
- 2510680 的 4 条 pending 不并入：本地 b2510680 期次备查已裁决（4 条 item 全部无锚点放弃）+ abandoned 4 条留痕，云端系重复推送。
- 2510217（云端 abandon vs 本地 pool）/2510857（云端 v8.0 verdict vs 本地 v8.5 复核改写）：本地为最新正确裁决，保留本地。
"""
import re, json

h = open('index.html', encoding='utf-8').read()
m = re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>', h, re.S)
d = json.loads(m.group(1))
assert d['version'] == '8.5' and len(d['watchlist']) == 36 and len(d['batches']) == 33, '母版基线不符'

hc = open('/tmp/cloud_index.html', encoding='utf-8').read()
c = json.loads(re.search(r'<script id="MONITOR_DATA" type="application/json">(.*?)</script>', hc, re.S).group(1))


def wkey(x):
    return (x.get('aid'), (x.get('bullet') or '')[:50])


lk = {wkey(x) for x in d['webcheck']}

added = []
for x in c['webcheck']:
    k = wkey(x)
    if k in lk:
        continue
    # 2510680：本地已裁决（batches+abandoned 双留痕），云端重复推送跳过
    if x.get('aid') == '2510680':
        continue
    if x.get('status') != 'pending':
        continue  # 只并 pending（pool/abandon 均以本地 v8.5 裁决为准）
    d['webcheck'].append(x)
    added.append(x['aid'])

print('并入云端新 pending：%d 条 → %s' % (len(added), sorted(set(added))))
assert len(added) == 3, added

pool_n = sum(1 for x in d['webcheck'] if x['status'] == 'pool')
aband_n = sum(1 for x in d['webcheck'] if x['status'] == 'abandon')
pend_n = sum(1 for x in d['webcheck'] if x['status'] == 'pending')
print('webcheck 三轨：pool=%d abandon=%d pending=%d 总=%d' % (pool_n, aband_n, pend_n, len(d['webcheck'])))
assert (pool_n, aband_n, pend_n, len(d['webcheck'])) == (37, 34, 3, 74)

# 写回（保持原有缩进风格：indent=1 + ensure_ascii=False）
new_json = json.dumps(d, ensure_ascii=False, indent=1)
h2 = h[:m.start(1)] + new_json + h[m.end(1):]
open('index.html', 'w', encoding='utf-8').write(h2)
print('index.html 已写回（MONITOR_DATA 仅 webcheck +3，其余不变）')

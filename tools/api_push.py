#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通过 GitHub Git Data API 推送（沙箱 git 协议不通时的通道）。
流程：取远端 ref → 建 blobs → 基于远端 tree 建新 tree → 建 commit → 快进更新 ref。
仅标准库。Token 从 /root/.codebuddy/monitor-mcp/.gh_push_token 读取（600 权限，不明文入脚本）。"""
import base64
import json
import os
import sys
import urllib.request

TOKEN_FILE = '/root/.codebuddy/monitor-mcp/.gh_push_token'
TOKEN = open(TOKEN_FILE).read().strip()
OWNER, REPO, BRANCH = 'guokexuan0522', 'cailianshe-dashboard', 'main'
API = 'https://api.github.com/repos/%s/%s' % (OWNER, REPO)
LOCAL = '/workspace/cailianshe-dashboard'

# 相对路径 → 本地文件（本次要推送的全部变更）
FILES = [
    'index.html',
    'refresh.py',
    'pending/【公告全知道】PCB+光模块+卫星通信+华为！公司1.6T交换机产品进入小批量量产.json',
    'pending/【狙击龙虎榜】指数分化暗藏变盘信号_题材轮动聚焦超跌机会.json',
    'pending/【财联社早知道】TrendForce预估2026年全球光纤供需缺口达1.8亿芯公里，现货价格年增2.8至5倍，机构称国内.json',
    'pending/【风口研报·洞察】红利资产近期超额收益显著，这个细分行业具备现金流改善叠加高股息属性，防御与弹性兼备；科技筹码出清到哪一.json',
    'pending/_scan_status.json',
]
MSG = ('feat: v5.4 核验入池试跑——12只新标的写入母版（在池26→38）+ refresh K线接口兼容修复\n\n'
       '- 第三层定时唤醒核验流水线首次全链路试跑：10-19四篇工单逐篇公开信源取证\n'
       '- 入池：生益电子/协创数据/三峡新材（公告全知道）、长进光子/天娱数科/众生药业（早知道）、\n'
       '  东安动力/能科科技/慈文传媒（狙击龙虎榜）、宏川智慧/顺丰控股/振华股份（风口研报洞察）\n'
       '- refresh.py：fetch_kline 兼容 qfqday/day 两种返回字段（部分标的如 sh688635 返回 day）\n'
       '- 行情/分时/K线同步至2026-10-19收盘，量化引擎重算12只技术评分')


def api(method, path, body=None, timeout=300):
    url = path if path.startswith('http') else API + path
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        'Authorization': 'token ' + TOKEN,
        'Accept': 'application/vnd.github+json',
        'Content-Type': 'application/json',
        'User-Agent': 'cailianshe-bot',
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def main():
    # 1. 远端当前 ref 与 commit/tree
    ref = api('GET', '/git/ref/heads/%s' % BRANCH)
    head = ref['object']['sha']
    commit = api('GET', '/git/commits/' + head)
    base_tree = commit['tree']['sha']
    print('远端 %s = %s | base_tree = %s' % (BRANCH, head[:8], base_tree[:8]))

    # 2. 逐文件建 blob
    tree = []
    for rel in FILES:
        p = os.path.join(LOCAL, rel)
        raw = open(p, 'rb').read()
        blob = api('POST', '/git/blobs', {
            'content': base64.b64encode(raw).decode('ascii'),
            'encoding': 'base64',
        }, timeout=300)
        tree.append({'path': rel, 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
        print('  blob %-70s %8d bytes' % (rel[:70], len(raw)))

    # 3. 基于远端 tree 建新 tree（只含变更路径）
    new_tree = api('POST', '/git/trees', {'base_tree': base_tree, 'tree': tree})
    print('新 tree =', new_tree['sha'][:8])

    # 4. 建 commit（父=远端头，保证快进）
    new_commit = api('POST', '/git/commits', {
        'message': MSG, 'tree': new_tree['sha'], 'parents': [head],
    })
    print('新 commit =', new_commit['sha'][:8])

    # 5. 快进更新 ref
    upd = api('PATCH', '/git/refs/heads/%s' % BRANCH, {'sha': new_commit['sha'], 'force': False})
    print('ref 更新成功：%s -> %s' % (BRANCH, upd['object']['sha'][:8]))
    return 0


if __name__ == '__main__':
    sys.exit(main())

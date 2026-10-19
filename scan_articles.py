#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""财联社·投研看板 云端文章扫描器（GitHub Actions 每 30 分钟触发）

职责（与 collect.py 的分工）：
  - collect.py  close  ：收盘后全量刷新行情/分时/K线/复盘 → 写 index.html
  - scan_articles.py   ：全自动文章发现 → 过门槛新文章写入仓库 pending/ 待核验队列
                          （不碰 index.html，不升版，不入池——入池须会话内核验，铁律）

设计原则：
  - 采集逻辑一行不改：直接复用 refresh.check_articles()
    （cls.cn 签名 API 11 栏目扫描 + 价格门槛 + 时间窗 + 失败不标记已见自动重试）。
  - 只重绑路径：pending/ 与 seen/ 持久化到仓库内（提交后不丢失，跨运行共享记忆），
    其余副作用（锁/日志/状态/feed）落 /tmp。
  - seen 种子：仓库 seen/seen_articles.json 已预置本地 692 条历史已见标题，
    云端不会重复发现 2026-10-11 之前的积压文章。

用法: python3 scan_articles.py
输出: 一行 JSON（ok/new/skipped/failed），供 workflow 日志查看。
"""
import json
import os
import sys
import datetime

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)
import refresh  # noqa: E402  复用本地采集核心（不改一行采集逻辑）

# ---- 重绑定路径：pending/seen 持久化进仓库；副作用落 /tmp ----
refresh.PENDING_DIR = os.path.join(REPO, 'pending')
refresh.SEEN_PATH = os.path.join(REPO, 'seen', 'seen_articles.json')
refresh.LOCK_PATH = '/tmp/cls_scan.lock'
refresh.LOG_PATH = '/tmp/cls_scan.log'
refresh.STATUS_PATH = '/tmp/cls_scan_status.json'
refresh.FEED_PATH = '/tmp/cls_feed.json'


def main():
    os.makedirs(refresh.PENDING_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(refresh.SEEN_PATH), exist_ok=True)
    try:
        r = refresh.check_articles()
    except Exception as e:
        out = {'ok': False, 'stage': 'run',
               'error': '%s: %s' % (type(e).__name__, e)}
        print(json.dumps(out, ensure_ascii=False))
        return 1

    # 扫描摘要（可观测：失败清单带原因，供排查；不标记已见的文章下轮自动重试）
    summary = {
        'lastScanAt': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'ok': bool(r.get('ok')),
        'new': r.get('new', 0),
        'skipped': r.get('skipped', 0),
        'failed': r.get('failed', 0),
        'source': r.get('source', ''),
        'note': r.get('note', ''),
        'newTitles': (r.get('titles') or [])[:20],
        'failedList': (r.get('failedList') or [])[:10],
    }
    with open(os.path.join(refresh.PENDING_DIR, '_scan_status.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)

    out = {'ok': bool(r.get('ok')), 'new': r.get('new', 0),
           'skipped': r.get('skipped', 0), 'failed': r.get('failed', 0),
           'source': r.get('source', ''), 'note': r.get('note', '')}
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())

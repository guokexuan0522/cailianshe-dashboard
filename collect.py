#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""财联社·投研看板 云端采集入口（GitHub Actions 定时触发）

设计原则（遵循《云端自动刷新改造方法》指南）：
  - 数据采集逻辑【完全不动】：直接复用本地采集核心 refresh.py
    （行情/分时/K线/复盘数值同步 + 文章公开信息检索），API、门槛、算法一律照搬。
  - 只改【产出与分发方式】：把刷新目标从本地母版改为仓库内 index.html，
    把副作用目录（锁/状态/日志/待核验队列）指向 /tmp，避免污染仓库 / 被误提交。
  - 不改动 version、不新增入池标的、不写研判结论（这些由人工会话完成）。

用法: python3 collect.py close | night
输出: 一行 JSON（ok/job/changed/session/skipped/reason），供 workflow 日志查看。
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)
import refresh  # noqa: E402  复用本地采集核心（不改一行采集逻辑）

# ---- 重绑定路径：产出到仓库 index.html；副作用落 /tmp，不进仓库 ----
refresh.HTML_PATH = os.path.join(REPO, 'index.html')
refresh.BASE_DIR = REPO
refresh.PENDING_DIR = '/tmp/cls_pending'
refresh.SEEN_PATH = '/tmp/cls_seen.json'
refresh.LOCK_PATH = '/tmp/cls_refresh.lock'
refresh.STATUS_PATH = '/tmp/cls_status.json'
refresh.LOG_PATH = '/tmp/cls_daemon.log'
refresh.FEED_PATH = '/tmp/cls_feed.json'


def main():
    job = sys.argv[1] if len(sys.argv) > 1 else 'close'
    if job not in ('close', 'night'):
        print(json.dumps({'ok': False, 'stage': 'args',
                          'error': 'job 必须是 close/night'}, ensure_ascii=False))
        return 2
    try:
        r = refresh.run(job)
    except Exception as e:
        print(json.dumps({'ok': False, 'stage': 'run',
                          'error': '%s: %s' % (type(e).__name__, e)}, ensure_ascii=False))
        return 1
    # refresh.run 的返回都视为“已成功处理”：
    #   ok=True            正常刷新（写盘）
    #   ok=True+skipped    护栏跳过（非交易时段/数据未更新）——同样记 ok
    #   ok=False           真实失败（网络/读取等）——如实报错
    out = {'ok': bool(r.get('ok')), 'job': job, 'changed': r.get('changed'),
           'session': r.get('session'), 'skipped': r.get('skipped'), 'reason': r.get('reason')}
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out['ok'] or r.get('skipped') else 1


if __name__ == '__main__':
    sys.exit(main())

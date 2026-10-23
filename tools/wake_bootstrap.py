#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""唤醒任务·裸沙箱自举脚本（v8.7 新增）。

解决「定时唤醒任务跑在未配置沙箱」问题：不依赖 git clone（github.com 在沙箱内不可达）、
不依赖任何本地历史路径，只走 codeload.github.com 匿名下载公开仓库 tarball。

用法：
  python3 wake_bootstrap.py [--dest /workspace/cls-repo] [--branch main]

产出：
  <dest>/cailianshe-dashboard-<branch>/   —— 解压后的完整仓库（含 index.html、tools/、pending/、autopool/、refresh.py）
   stdout 最后一行打印：REPO_DIR=<绝对路径>   （供 shell eval 使用）

验证（在唤醒沙箱执行）：
  python3 wake_bootstrap.py && ls "$REPO_DIR/tools/"
"""
import argparse
import io
import os
import sys
import tarfile
import urllib.request

OWNER, REPO = 'guokexuan0522', 'cailianshe-dashboard'
CODELOAD = 'https://codeload.github.com/%s/%s/tar.gz/refs/heads/%s'


def main():
    ap = argparse.ArgumentParser(description='下载并解压财联社看板仓库（codeload tarball）')
    ap.add_argument('--dest', default='/workspace/cls-repo', help='解压目标目录')
    ap.add_argument('--branch', default='main', help='分支名')
    args = ap.parse_args()

    url = CODELOAD % (OWNER, REPO, args.branch)
    print('下载 %s ...' % url)
    req = urllib.request.Request(url, headers={'User-Agent': 'cailianshe-wake-bot'})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = r.read()
    except Exception as e:  # noqa: BLE001
        sys.stderr.write('错误：tarball 下载失败 %r\n' % e)
        return 1
    print('下载完成 %d bytes' % len(data))

    os.makedirs(args.dest, exist_ok=True)
    # 解压前清理旧副本，保证每次唤醒都是云端最新
    expect = '%s-%s' % (REPO, args.branch)
    old = os.path.join(args.dest, expect)
    if os.path.isdir(old):
        import shutil
        shutil.rmtree(old)
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tf:
        tf.extractall(args.dest)

    repo_dir = old
    # 自检关键依赖
    checks = ['index.html', 'tools/WAKE_RUNBOOK.md', 'tools/api_push.py',
              'tools/calc_signals.py', 'tools/verify_ledger.jsonl', 'refresh.py']
    missing = [c for c in checks if not os.path.isfile(os.path.join(repo_dir, c))]
    if missing:
        sys.stderr.write('错误：仓库缺少关键文件 %s\n' % missing)
        return 1
    print('解压完成：%s' % repo_dir)
    print('关键依赖自检通过：%s' % ', '.join(checks))
    print('REPO_DIR=%s' % repo_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main())

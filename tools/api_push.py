#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通过 GitHub Git Data API 推送（沙箱 git 协议不通时的唯一可靠通道）。

流程：取远端 ref → 建 blobs → 基于远端 tree 建新 tree → 建 commit → 快进更新 ref。
仅标准库。域名 api.github.com 在沙箱内可达（github.com / raw.githubusercontent 不可达，git clone 不可用）。

Token 读取优先级（均为不明文入脚本）：
  1. 环境变量 GH_TOKEN
  2. 脚本同目录 .gh_push_token
  3. /root/.codebuddy/monitor-mcp/.gh_push_token（主沙箱历史位置）

用法：
  GH_TOKEN=xxx python3 api_push.py --base /workspace/cls-repo/cailianshe-dashboard-main \
      --files index.html,tools/verify_ledger.jsonl --msg "wake: v8.7 入池..."

  # 不指定 --files 时默认推送 index.html 与 tools/verify_ledger.jsonl（若存在）。
  # --base 默认为当前工作目录。
  # --rebase-retry N：non-fast-forward 时按新 HEAD 重建重试 N 次（默认 0）。
  #   仅限「唤醒侧独占 + 只追加」文件（tools/verify_ledger.jsonl）——逐篇核验逐篇推送，
  #   超时/并发也不丢进度；严禁用于 index.html（会覆盖云端 land.py 并发落地，脚本内已拦截）。
"""
import argparse
import base64
import json
import os
import sys
import urllib.request

OWNER, REPO, BRANCH = 'guokexuan0522', 'cailianshe-dashboard', 'main'
API = 'https://api.github.com/repos/%s/%s' % (OWNER, REPO)
DEFAULT_FILES = ['index.html', 'tools/verify_ledger.jsonl']
TOKEN_CANDIDATES = [
    os.environ.get('GH_TOKEN'),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '.gh_push_token'),
    '/root/.codebuddy/monitor-mcp/.gh_push_token',
]


def load_token():
    for p in TOKEN_CANDIDATES:
        if p and os.path.isfile(p):
            t = open(p, encoding='utf-8').read().strip()
            if t:
                return t
    sys.stderr.write('错误：未找到 GitHub 令牌。请设置环境变量 GH_TOKEN，'
                     '或将令牌写入脚本同目录 .gh_push_token（或 /root/.codebuddy/monitor-mcp/.gh_push_token）。\n')
    sys.exit(2)


TOKEN = load_token()


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


def push_with_retry(files, base, msg, rebase_retry=0):
    """推送并在 non-fast-forward 时按新 HEAD 重建重试。

    安全边界（重要）：
      - rebase-retry 只允许用于「唤醒侧独占 + 只追加」的文件（tools/verify_ledger.jsonl）：
        重试只是把同一个 tree 挂到新的远端 HEAD 后面，文件内容不重合并。
      - index.html 严禁带 rebase-retry：唤醒本地母版基于旧 HEAD 构建，
        盲目重试会覆盖云端 land.py 的并发落地条目（数据丢失）。母版推送遇 422
        应如实报告「推送受阻」，留待下轮重做——失败是安全的，覆盖才危险。
    """
    if rebase_retry > 0 and any('index.html' in f for f in files):
        sys.stderr.write('错误：index.html 不允许带 --rebase-retry（有覆盖云端并发落地的风险）\n')
        return 1

    attempt = 0
    while True:
        attempt += 1
        # 1. 远端当前 ref 与 commit/tree
        ref = api('GET', '/git/ref/heads/%s' % BRANCH)
        head = ref['object']['sha']
        commit = api('GET', '/git/commits/' + head)
        base_tree = commit['tree']['sha']
        print('远端 %s = %s | base_tree = %s（第 %d 次尝试）' % (BRANCH, head[:8], base_tree[:8], attempt))

        # 2. 逐文件建 blob
        tree = []
        for rel in files:
            raw = open(os.path.join(base, rel), 'rb').read()
            blob = api('POST', '/git/blobs', {
                'content': base64.b64encode(raw).decode('ascii'),
                'encoding': 'base64',
            }, timeout=300)
            tree.append({'path': rel, 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
            print('  blob %-70s %8d bytes' % (rel[:70], len(raw)))

        # 3+4. 基于远端 tree 建新 tree 与 commit
        new_tree = api('POST', '/git/trees', {'base_tree': base_tree, 'tree': tree})
        new_commit = api('POST', '/git/commits', {
            'message': args_msg, 'tree': new_tree['sha'], 'parents': [head],
        })
        print('新 tree = %s | 新 commit = %s' % (new_tree['sha'][:8], new_commit['sha'][:8]))

        # 5. 快进更新 ref；non-fast-forward 时按需重试
        try:
            upd = api('PATCH', '/git/refs/heads/%s' % BRANCH,
                      {'sha': new_commit['sha'], 'force': False})
            print('ref 更新成功：%s -> %s' % (BRANCH, upd['object']['sha'][:8]))
            return 0
        except urllib.error.HTTPError as e:
            body = ''
            try:
                body = e.read().decode('utf-8', 'replace')[:200]
            except Exception:
                pass
            if attempt <= rebase_retry:
                print('non-fast-forward（%s），按新 HEAD 重试 %d/%d' % (body, attempt, rebase_retry))
                continue
            sys.stderr.write('推送失败 HTTP %s：%s\n' % (e.code, body))
            return 1


def main():
    global args_msg
    ap = argparse.ArgumentParser(description='GitHub Git Data API 推送')
    ap.add_argument('--base', default='.', help='本地工作目录（仓库根），默认当前目录')
    ap.add_argument('--files', default='', help='逗号分隔的相对路径；缺省推送 index.html 与 tools/verify_ledger.jsonl')
    ap.add_argument('--msg', required=True, help='commit message')
    ap.add_argument('--rebase-retry', type=int, default=0,
                    help='non-fast-forward 时按新 HEAD 重建重试的次数（默认 0）；'
                         '仅限唤醒侧独占的只追加文件（verify_ledger.jsonl），严禁用于 index.html')
    args = ap.parse_args()
    args_msg = args.msg

    files = [f.strip() for f in args.files.split(',') if f.strip()] if args.files else list(DEFAULT_FILES)
    # 缺省文件不存在则跳过；显式指定的文件必须存在
    explicit = bool(args.files)
    existing = []
    for rel in files:
        p = os.path.join(args.base, rel)
        if os.path.isfile(p):
            existing.append(rel)
        elif explicit:
            sys.stderr.write('错误：文件不存在 %s\n' % p)
            return 1
    if not existing:
        print('无文件可推送（目标均不存在），退出')
        return 0

    return push_with_retry(existing, args.base, args.msg, rebase_retry=args.rebase_retry)


if __name__ == '__main__':
    sys.exit(main())

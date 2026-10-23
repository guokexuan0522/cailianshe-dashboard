#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""唤醒沙箱环境自检（wake_env_check）——第三层唤醒任务的只读诊断工具。

用途：定时唤醒任务跑在隔离裸沙箱，网络可达性与工具可用性一直是黑盒。
本脚本一次性探测关键端点与环境指纹，把结果推送至仓库的 refs/heads/wake-diag
分支（与 main/Pages 完全隔离，只写诊断分支，严禁碰 main），供人工会话直接读取。

探测项：
  1. codeload.github.com（tarball 自举通道）——下载 main 分支 tarball 并记录字节数
  2. api.github.com（Git Data API 推送通道，需令牌）——带令牌 GET 仓库 contents
  3. qt.gtimg.cn（行情采集通道）
  4. www.cls.cn（信息源站点）
  5. github.com（预期不可达，记录佐证）
  6. 环境指纹：uname / /workspace 列表 / 关键目录存在性 / python3 版本

用法（唤醒沙箱内）：
  GH_TOKEN=<令牌> python3 tools/wake_env_check.py
退出码：0=全部关键通道（codeload+api）通畅；1=有关键通道不通（详情见报告）。
"""
import json
import os
import platform
import subprocess
import sys
import time
import urllib.request
import urllib.error

OWNER, REPO = "guokexuan0522", "cailianshe-dashboard"
API = "https://api.github.com/repos/%s/%s" % (OWNER, REPO)
DIAG_BRANCH = "wake-diag"
TOKEN = os.environ.get("GH_TOKEN", "").strip()


def http_probe(url, headers=None, timeout=15, max_bytes=200):
    """返回 (http_code, 响应前 max_bytes 字符或错误摘要, 耗时ms)"""
    req = urllib.request.Request(url, headers=headers or {})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(max_bytes).decode("utf-8", "replace")
            return r.status, body, int((time.time() - t0) * 1000)
    except urllib.error.HTTPError as e:
        return e.code, "HTTPError", int((time.time() - t0) * 1000)
    except Exception as e:
        return -1, "%s: %s" % (type(e).__name__, str(e)[:120]), int((time.time() - t0) * 1000)


def run(cmd, timeout=20):
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (out.stdout or "").strip()[:500]
    except Exception as e:
        return "ERR %s" % e


def api(method, path, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={
        "Authorization": "token " + TOKEN,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "cailianshe-wake-diag",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def push_diag_branch(report_text):
    """把报告推送至 refs/heads/wake-diag（与 main 隔离）"""
    if not TOKEN:
        return "跳过（无 GH_TOKEN）"
    head = api("GET", "/git/ref/heads/main")["object"]["sha"]
    blob = api("POST", "/git/blobs", {
        "content": report_text, "encoding": "utf-8"})
    tree = api("POST", "/git/trees", {
        "base_tree": api("GET", "/git/commits/" + head)["tree"]["sha"],
        "tree": [{"path": "wake_env_check.json", "mode": "100644", "type": "blob", "sha": blob["sha"]}],
    })
    commit = api("POST", "/git/commits", {
        "message": "wake-env-check %s" % time.strftime("%Y-%m-%d %H:%M:%S"),
        "tree": tree["sha"], "parents": [head],
    })
    try:
        api("POST", "/git/refs", {"ref": "refs/heads/" + DIAG_BRANCH, "sha": commit["sha"]})
        action = "created"
    except urllib.error.HTTPError:
        api("PATCH", "/git/refs/heads/" + DIAG_BRANCH, {"sha": commit["sha"], "force": True})
        action = "updated"
    return "%s refs/heads/%s -> %s" % (action, DIAG_BRANCH, commit["sha"][:8])


def main():
    report = {"time": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "probes": {}, "env": {}}
    auth = {"Authorization": "token " + TOKEN} if TOKEN else {}

    # 1. codeload 自举通道
    code, body, ms = http_probe(
        "https://codeload.github.com/%s/%s/tar.gz/refs/heads/main" % (OWNER, REPO),
        timeout=60, max_bytes=64)
    report["probes"]["codeload"] = {"http": code, "ms": ms, "note": body[:64]}
    # 2. api.github.com 推送通道（带令牌）
    code2, body2, ms2 = http_probe(API + "/contents/tools", headers=auth, timeout=20)
    report["probes"]["api_github"] = {"http": code2, "ms": ms2, "note": body2[:80]}
    # 3. 行情通道
    code3, body3, ms3 = http_probe("https://qt.gtimg.cn/q=sh600000", timeout=15)
    report["probes"]["qt_gtimg"] = {"http": code3, "ms": ms3, "note": body3[:80]}
    # 4. 信息源站点
    code4, body4, ms4 = http_probe("https://www.cls.cn/", timeout=15)
    report["probes"]["cls_cn"] = {"http": code4, "ms": ms4, "note": body4[:80]}
    # 5. github.com（预期不通）
    code5, body5, ms5 = http_probe("https://github.com/", timeout=8)
    report["probes"]["github_com"] = {"http": code5, "ms": ms5, "note": body5[:80]}
    # 6. 环境指纹
    report["env"] = {
        "uname": run("uname -a"),
        "python": run("python3 --version"),
        "workspace": run("ls -la /workspace 2>&1 | head -20"),
        "has_monitor_mcp": os.path.exists("/root/.codebuddy/monitor-mcp"),
        "has_codebuddy": os.path.exists("/root/.codebuddy"),
        "pwd_after_bootstrap": run("ls /workspace/cls-repo 2>&1 | head -5"),
        "token_present": bool(TOKEN),
    }

    critical_ok = report["probes"]["codeload"]["http"] == 200 and report["probes"]["api_github"]["http"] == 200
    report["verdict"] = "PASS" if critical_ok else "FAIL"

    text = json.dumps(report, ensure_ascii=False, indent=1)
    print(text)
    push_note = push_diag_branch(text)
    print("PUSH:", push_note)
    return 0 if critical_ok else 1


if __name__ == "__main__":
    sys.exit(main())

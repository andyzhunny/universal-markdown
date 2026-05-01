#!/usr/bin/env python3
"""
gh-publish.py — 一键将本地文件夹发布到 GitHub

用法:
    python gh-publish.py <本地文件夹路径> <仓库名> [GitHub PAT]

环境变量（推荐）:
    GITHUB_TOKEN  — 你的 GitHub Personal Access Token（带 repo 权限）

示例:
    python gh-publish.py "C:\\path\\to\\my-project" "my-project"
    python gh-publish.py "C:\\path\\to\\my-project" "my-project" "ghp_xxxx"
    set GITHUB_TOKEN=ghp_xxxx && python gh-publish.py "C:\\path\\to\\my-project" "my-project"
"""

import os
import sys
import subprocess
import requests
from pathlib import Path


# ─────────────────────────────────────────
# 配置区（可选填入默认值）
# ─────────────────────────────────────────
DEFAULT_GITHUB_USERNAME = "andyzhunny"   # 修改为你的 GitHub 用户名
DEFAULT_TOKEN = ""                         # 推荐通过环境变量 GITHUB_TOKEN 传入，勿硬编码
# ─────────────────────────────────────────


def get_token() -> str:
    token = os.environ.get("GITHUB_TOKEN") or DEFAULT_TOKEN or (sys.argv[3] if len(sys.argv) > 3 else "")
    if not token:
        print("[错误] 未提供 GitHub Token")
        print("  方式一（推荐）: set GITHUB_TOKEN=ghp_xxxx && python gh-publish.py <folder> <name>")
        print("  方式二: python gh-publish.py <folder> <name> <token>")
        sys.exit(1)
    return token


def get_username(token: str) -> str:
    r = requests.get("https://api.github.com/user", headers={"Authorization": f"token {token}"})
    if r.status_code != 200:
        print(f"[错误] Token 无效，状态码: {r.status_code}")
        sys.exit(1)
    return r.json()["login"]


def repo_exists(username: str, repo_name: str, token: str) -> bool:
    r = requests.get(f"https://api.github.com/repos/{username}/{repo_name}",
                      headers={"Authorization": f"token {token}"})
    return r.status_code == 200


def create_repo(username: str, repo_name: str, token: str) -> bool:
    if repo_exists(username, repo_name, token):
        print(f"[提示] 仓库 {username}/{repo_name} 已存在，跳过创建。")
        return True

    r = requests.post(
        "https://api.github.com/user/repos",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        },
        json={
            "name": repo_name,
            "description": f"Published with gh-publish.py",
            "private": False,
            "has_issues": True,
            "has_wiki": False,
            "auto_init": False
        }
    )
    if r.status_code == 201:
        print(f"[创建] 仓库 {username}/{repo_name} 创建成功 ✓")
        return True
    else:
        print(f"[错误] 创建仓库失败: {r.status_code} — {r.text}")
        return False


def git_publish(folder: Path, repo_name: str, username: str, token: str) -> None:
    folder = folder.resolve()
    if not folder.is_dir():
        print(f"[错误] 路径不存在或不是文件夹: {folder}")
        sys.exit(1)

    remote_url = f"https://{username}:{token}@github.com/{username}/{repo_name}.git"
    git_dir = folder / ".git"

    if git_dir.exists():
        # 已初始化，检查 remote
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=folder, capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"[Git] remote origin 已存在: {result.stdout.strip()}")
            print(f"[Git] 跳过 init，直接 push。")
            subprocess.run(["git", "push", "-u", "origin", "HEAD", "--force"],
                          cwd=folder, check=True)
            print("[完成] 已强制推送到现有仓库 ✓")
            return
    else:
        subprocess.run(["git", "init", "-b", "main"], cwd=folder, check=True)
        print("[Git] git init 完成")

    # 配置 user（如果全局没有）
    for key, val in [("user.name", "gh-publish"), ("user.email", "gh@publish.local")]:
        r = subprocess.run(["git", "config", f"user.{key.split('.')[1]}", val],
                           cwd=folder, capture_output=True)
        del r  # 忽略是否覆盖

    # .gitignore 兜底
    gitignore = folder / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("converted/\n__pycache__/\n*.pyc\n.env\n")
        print("[文件] 已创建 .gitignore")

    subprocess.run(["git", "add", "-A"], cwd=folder, check=True)

    # 检查是否有变更需要提交
    status = subprocess.run(["git", "status", "--porcelain"],
                            cwd=folder, capture_output=True, text=True)
    if status.stdout.strip():
        subprocess.run(
            ["git", "commit", "-m", f"Publish {repo_name}"],
            cwd=folder, check=True
        )
        print("[Git] git commit 完成")
    else:
        print("[Git] 无变更需要提交")

    # 设置 remote
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=folder, capture_output=True, text=True
    )
    if result.returncode != 0:
        subprocess.run(["git", "remote", "add", "origin", remote_url], cwd=folder, check=True)
        print("[Git] remote origin 已添加")
    else:
        # 更新 remote URL
        subprocess.run(["git", "remote", "set-url", "origin", remote_url], cwd=folder, check=True)
        print("[Git] remote origin URL 已更新")

    subprocess.run(["git", "push", "-u", "origin", "HEAD", "--force"],
                   cwd=folder, check=True)
    print("[完成] 推送成功 ✓")


def main():
    if len(sys.argv) < 3:
        print("用法: python gh-publish.py <文件夹路径> <仓库名> [GitHub PAT]")
        print()
        print("环境变量（推荐）: GITHUB_TOKEN")
        print("  Windows: set GITHUB_TOKEN=ghp_xxxx")
        print("  macOS/Linux: export GITHUB_TOKEN=ghp_xxxx")
        print()
        print("示例:")
        print("  python gh-publish.py \"C:\\project\\my-skill\" \"my-skill\"")
        print("  python gh-publish.py \"/home/user/project\" \"my-project\" \"ghp_xxxx\"")
        sys.exit(1)

    folder = Path(sys.argv[1])
    repo_name = sys.argv[2].strip()
    token = get_token()

    # 仓库名合法性检查（GitHub 限制）
    invalid = "/\\ :?*\"<>|"
    for c in invalid:
        if c in repo_name:
            print(f"[错误] 仓库名不能包含特殊字符: {invalid}")
            sys.exit(1)

    username = get_username(token)
    print(f"[用户] {username}")
    print(f"[仓库] {repo_name}")
    print()

    if not create_repo(username, repo_name, token):
        sys.exit(1)

    git_publish(folder, repo_name, username, token)

    print()
    print(f"访问: https://github.com/{username}/{repo_name}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
GitHub Issues表示スクリプト

指定されたリポジトリまたは組織のissuesを取得し、
結果を標準出力とMarkdownファイルに出力します。
"""

import os
import sys
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# ==========================================
# 設定セクション（ここを編集してください）
# ==========================================

# GitHub組織名またはユーザー名
OWNER = "microfund"

# リポジトリ名（Noneの場合は組織全体のissuesを取得）
REPOSITORY = "freee-public"  # 例: "example-repo" または None

# issuesの状態フィルター（"open", "closed", "all"）
STATE = "open"

# 取得する最大issue数
MAX_ISSUES = 100

# ==========================================
# 環境変数とトークン管理
# ==========================================

def load_env_file() -> None:
    """
    .envファイルから環境変数を読み込む
    
    スクリプトと同じディレクトリの.envファイルを読み込む
    """
    # スクリプトのディレクトリを取得
    script_dir = Path(__file__).resolve().parent
    env_path = script_dir / ".env"
    
    if not env_path.exists():
        # カレントディレクトリも確認
        env_path = Path(".env")
        if not env_path.exists():
            return
    
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value:
                        os.environ.setdefault(key, value)
    except Exception as e:
        print(f"警告: .envファイルの読み込みに失敗しました: {e}", file=sys.stderr)


def get_github_token() -> Optional[str]:
    """
    GitHub Personal Access Tokenを取得
    
    優先順位:
    1. 環境変数 GITHUB_TOKEN
    2. 環境変数 GITHUB_PAT
    3. .envファイルから読み込み
    
    Returns:
        GitHubトークン、または取得できない場合はNone
    """
    # .envファイルから環境変数を読み込み
    script_dir = Path(__file__).resolve().parent
    env_path = script_dir / ".env"
    
    print(f"スクリプトディレクトリ: {script_dir}", file=sys.stderr)
    print(f".envファイルパス: {env_path}", file=sys.stderr)
    print(f".envファイル存在確認: {env_path.exists()}", file=sys.stderr)
    
    load_env_file()
    
    # 環境変数から取得を試みる
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_PAT")
    
    if token:
        print(f"トークン取得成功（長さ: {len(token)}文字）", file=sys.stderr)
    
    if not token:
        print("\nエラー: GitHub Personal Access Tokenが設定されていません。", file=sys.stderr)
        print("以下のいずれかの方法でトークンを設定してください:", file=sys.stderr)
        print(f"  1. 環境変数 GITHUB_TOKEN を設定", file=sys.stderr)
        print(f"  2. {env_path} に GITHUB_TOKEN=your_token_here を記述", file=sys.stderr)
        print("\nトークンの作成方法:", file=sys.stderr)
        print("  https://github.com/settings/tokens", file=sys.stderr)
        print("  必要な権限: repo (リポジトリ全体へのアクセス)", file=sys.stderr)
        
        # .envファイルのサンプルを表示
        if not env_path.exists():
            print(f"\n.envファイルが見つかりません。以下の内容で作成してください:", file=sys.stderr)
            print(f"  ファイルパス: {env_path}", file=sys.stderr)
            print(f"  内容例:", file=sys.stderr)
            print(f'    GITHUB_TOKEN="ghp_your_token_here"', file=sys.stderr)
        
        return None
    
    return token


# ==========================================
# GitHub API関連の関数
# ==========================================

def get_issues_from_repo(
    session: requests.Session,
    owner: str,
    repo: str,
    state: str = "open",
    max_issues: int = 100
) -> List[Dict[str, Any]]:
    """
    特定のリポジトリからissuesを取得
    
    Args:
        session: requestsセッション
        owner: オーナー名
        repo: リポジトリ名
        state: issuesの状態
        max_issues: 取得する最大issue数
    
    Returns:
        issuesのリスト
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    params = {
        "state": state,
        "per_page": min(max_issues, 100),
        "sort": "updated",
        "direction": "desc"
    }
    
    all_issues = []
    page = 1
    
    while len(all_issues) < max_issues:
        params["page"] = page
        response = session.get(url, params=params)
        
        if response.status_code != 200:
            print(f"エラー: リポジトリ {owner}/{repo} のissues取得に失敗しました。", file=sys.stderr)
            print(f"ステータスコード: {response.status_code}", file=sys.stderr)
            print(f"レスポンス: {response.text}", file=sys.stderr)
            break
        
        issues = response.json()
        
        if not issues:
            break
        
        # プルリクエストを除外
        issues = [issue for issue in issues if "pull_request" not in issue]
        all_issues.extend(issues)
        
        if len(issues) < params["per_page"]:
            break
        
        page += 1
    
    return all_issues[:max_issues]


def get_org_issues(
    session: requests.Session,
    org: str,
    state: str = "open",
    max_issues: int = 100
) -> List[Dict[str, Any]]:
    """
    組織全体のissuesを取得
    
    Args:
        session: requestsセッション
        org: 組織名
        state: issuesの状態
        max_issues: 取得する最大issue数
    
    Returns:
        issuesのリスト
    """
    # まず組織のリポジトリ一覧を取得
    url = f"https://api.github.com/orgs/{org}/repos"
    params = {"per_page": 100, "type": "all"}
    
    response = session.get(url, params=params)
    
    if response.status_code != 200:
        print(f"エラー: 組織 {org} のリポジトリ一覧取得に失敗しました。", file=sys.stderr)
        print(f"ステータスコード: {response.status_code}", file=sys.stderr)
        return []
    
    repos = response.json()
    
    # 各リポジトリからissuesを取得
    all_issues = []
    
    for repo in repos:
        repo_name = repo["name"]
        issues = get_issues_from_repo(session, org, repo_name, state, max_issues)
        all_issues.extend(issues)
        
        if len(all_issues) >= max_issues:
            break
    
    # 更新日時でソート
    all_issues.sort(key=lambda x: x["updated_at"], reverse=True)
    
    return all_issues[:max_issues]


# ==========================================
# 出力関連の関数
# ==========================================

def format_issue_markdown(issue: Dict[str, Any]) -> str:
    """
    issue情報をMarkdown形式にフォーマット
    
    Args:
        issue: issue情報の辞書
    
    Returns:
        Markdown形式の文字列
    """
    number = issue["number"]
    title = issue["title"]
    state = issue["state"]
    user = issue["user"]["login"]
    created_at = issue["created_at"]
    updated_at = issue["updated_at"]
    html_url = issue["html_url"]
    labels = ", ".join([label["name"] for label in issue["labels"]]) if issue["labels"] else "なし"
    assignees = ", ".join([assignee["login"] for assignee in issue["assignees"]]) if issue["assignees"] else "なし"
    
    # リポジトリ名を取得
    repo_full_name = issue["repository_url"].split("/repos/")[1] if "repository_url" in issue else "不明"
    
    state_emoji = "🟢" if state == "open" else "🔴"
    
    markdown = f"""
### {state_emoji} #{number}: {title}

- **状態**: {state}
- **リポジトリ**: {repo_full_name}
- **作成者**: {user}
- **作成日時**: {created_at}
- **更新日時**: {updated_at}
- **ラベル**: {labels}
- **担当者**: {assignees}
- **URL**: {html_url}

---
"""
    return markdown


def save_to_markdown(issues: List[Dict[str, Any]], output_path: Path) -> None:
    """
    issues情報をMarkdownファイルに保存
    
    Args:
        issues: issuesのリスト
        output_path: 出力ファイルパス
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        # ヘッダー
        f.write(f"# GitHub Issues一覧\n\n")
        f.write(f"**生成日時**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**総issue数**: {len(issues)}\n\n")
        f.write("---\n")
        
        # 各issueを出力
        if issues:
            for issue in issues:
                f.write(format_issue_markdown(issue))
        else:
            f.write("\n該当するissuesが見つかりませんでした。\n")


def print_issues_summary(issues: List[Dict[str, Any]]) -> None:
    """
    issues情報の要約を標準出力に表示
    
    Args:
        issues: issuesのリスト
    """
    print(f"\n{'='*60}")
    print(f"GitHub Issues一覧")
    print(f"{'='*60}\n")
    print(f"総issue数: {len(issues)}\n")
    
    if issues:
        for issue in issues:
            number = issue["number"]
            title = issue["title"]
            state = issue["state"]
            repo_url = issue.get("repository_url", "")
            repo_name = repo_url.split("/")[-1] if repo_url else "不明"
            
            state_emoji = "🟢" if state == "open" else "🔴"
            print(f"{state_emoji} #{number}: {title}")
            print(f"   リポジトリ: {repo_name} | 状態: {state}")
            print(f"   URL: {issue['html_url']}")
            print()
    else:
        print("該当するissuesが見つかりませんでした。\n")


# ==========================================
# メイン処理
# ==========================================

def main():
    """メイン処理"""
    # トークンを取得
    token = get_github_token()
    if not token:
        sys.exit(1)
    
    # セッションを作成
    session = requests.Session()
    session.headers.update({
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    })
    
    print(f"GitHub issuesを取得中...\n")
    print(f"対象: {OWNER}")
    if REPOSITORY:
        print(f"リポジトリ: {REPOSITORY}")
    else:
        print(f"対象: 組織全体")
    print(f"状態フィルター: {STATE}")
    print(f"最大取得数: {MAX_ISSUES}\n")
    
    # issuesを取得
    if REPOSITORY:
        issues = get_issues_from_repo(session, OWNER, REPOSITORY, STATE, MAX_ISSUES)
    else:
        issues = get_org_issues(session, OWNER, STATE, MAX_ISSUES)
    
    # 標準出力に表示
    print_issues_summary(issues)
    
    # Markdownファイルに保存
    script_path = Path(__file__).resolve()
    output_path = script_path.parent / f"{script_path.stem}.md"
    
    save_to_markdown(issues, output_path)
    
    print(f"\n{'='*60}")
    print(f"結果を保存しました: {output_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
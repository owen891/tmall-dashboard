"""守卫：私有采集插件目录 collectors/ 绝不进入公开仓库。

背景（2026-10-23）：collectors/ 是嵌在项目内、但自成独立 git 仓库的私人采集插件，
外层 tmall-dashboard 仓库是公开的。一旦外层跟踪了该目录（如误用 git add -A，
或 .gitignore 规则被删后 add），采集实现与防风控细节就会随公开仓库泄露。

本测试做两道防呆：
1. .gitignore 必须保留 /collectors/ 规则（防规则被误删）；
2. git ls-files 输出不得出现 collectors（防绕过规则，如 git add -f）。

CI 云端 checkout 里没有 collectors/ 目录，两个断言自然通过，无副作用。
"""
import subprocess
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class PrivateCollectorsNotTrackedTest(unittest.TestCase):
    def test_gitignore_contains_collectors_rule(self):
        gitignore = PROJECT_ROOT / ".gitignore"
        text = gitignore.read_text(encoding="utf-8")
        self.assertIn(
            "/collectors/",
            text,
            ".gitignore 缺少 /collectors/ 规则：私有采集插件目录会被 git add -A 提交进公开仓库",
        )

    def test_collectors_not_tracked_by_git(self):
        proc = subprocess.run(
            ["git", "ls-files", "--", "collectors"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, f"git ls-files 失败：{proc.stderr}")
        tracked = [
            line
            for line in proc.stdout.splitlines()
            if line == "collectors" or line.startswith("collectors/")
        ]
        self.assertEqual(
            tracked,
            [],
            "公开仓库正在跟踪私有采集插件目录，用 git rm --cached -r collectors 撤销后重新提交",
        )


if __name__ == "__main__":
    unittest.main()

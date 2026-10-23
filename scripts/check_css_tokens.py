#!/usr/bin/env python
"""CSS 变量一致性检查：找出「被 var() 引用但从未定义」的 token（幽灵 token）。

用法：
    ./.venv/Scripts/python.exe scripts/check_css_tokens.py            # 只报告
    ./.venv/Scripts/python.exe scripts/check_css_tokens.py --strict   # 有幽灵 token 就退出码 1

为什么要查这个：
    幽灵 token 的两种失效方式都很隐蔽，**静态审计和截图都容易漏**：
      - 无 fallback  → `var(--x)` 是**无效声明**，整条属性消失。
        例：`color: var(--text-danger)` → 错误提示不是红的；
           `background: var(--primary-color); color: white` → 白字透明底，完全不可见。
      - 有 fallback  → 浅色正常，**暗色下塌掉**。
        例：`background: var(--surface-primary, #fff)` → 暗色模式卡片仍是白底，
           而文字取 `--text-primary`（暗色近白）→ 1.05:1，单页 97 项不可读。
    实测一次清理扫出 18 个幽灵 token、45 处引用。

判据：
    定义 = 任意 .css / .html 里的 `--x:` 声明，或任意 .js 里的 `setProperty('--x', ...)`。
    引用 = `var(--x)`，用 `(?![a-z0-9-])` 断言避免把 `--border-warning` 误判成 `--border-warning-subtle`。
    注释里的引用会被扫到（当前只有一处历史说明），用 WHITELIST 放行。

    **定义位置必须真的是自定义属性**：`--x` 前面不能紧邻标示符字符。
    否则 `.ui-button--primary:hover` 里的 `--primary:` 会被当成「定义了 --primary」，
    于是 `var(--primary)` 这种真错字永远查不出来（--primary/--success/--danger/
    --warning/--info 这 5 个当前正是这样被误登记的）。
"""
import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent / 'frontend' / 'ui_demo'

# 有意保留的「无定义」：key 是 token 名，value 是理由。
WHITELIST = {
    '--rule-depth': 'JS 将来按嵌套层级 setProperty；当前 CSS 里写的是 var(--rule-depth, 0) 兜底',
    '--surface-2': '只在 keyword-promotion.css 的历史注释里出现，不是活引用',
    # 以下三项是 2026-10 引入门禁时既存的历史引用，都带 fallback 因而渲染正常。
    # 它们与真实 token（--surface-muted / --border-default / --duration-fast）语义相近但取值不同，
    # 直接替换会改变现有观感，因此先登记豁免；新代码不得再引入这类幽灵引用。
    '--surface-subtle': 'period-review.css:2676 带 rgba fallback；与 --surface-muted 取值不同，替换会改观感',
    '--border-subtle': 'market-ranking-live.js:1072 内联样式带 #e5e7eb fallback；与 --border-default 取值相近但未对齐',
    '--transition-fast': 'period-review.css:2646 带 120ms fallback；真实 token 是 --duration-fast(160ms)，取值不同',
}


def scan(root: pathlib.Path):
    files = [p for p in root.rglob('*') if p.suffix in ('.css', '.html', '.js')]
    defined, used = set(), collections.defaultdict(set)
    # 自定义属性声明：`--x:`，且前面不能是 [A-Za-z0-9_-]。
    # 这条负向断言把 `.ui-button--primary:hover` 这类 BEM 修饰符排除掉——
    # 它们是选择器的一部分，不定义任何变量。
    declaration = re.compile(r'(?<![A-Za-z0-9_-])(--[a-z0-9-]+)\s*:')
    for f in files:
        s = f.read_text(encoding='utf-8')
        defined |= set(declaration.findall(s))                                      # CSS 声明
        defined |= set(re.findall(r'setProperty\(\s*[\'"`](--[a-z0-9-]+)', s))      # JS 动态
        for m in re.finditer(r'var\(\s*(--[a-z0-9-]+)(?![a-z0-9-])', s):
            used[m.group(1)].add(f.relative_to(root).as_posix())
    return defined, used


def main() -> int:
    # Windows 控制台默认 GBK，报告里的 emoji 会触发 UnicodeEncodeError，
    # 导致「发现问题时脚本自己崩掉」—— 门禁等于失效。统一降级为 ASCII 安全输出。
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass
    strict = '--strict' in sys.argv
    defined, used = scan(ROOT)
    missing = {k: sorted(v) for k, v in used.items() if k not in defined and k not in WHITELIST}

    print(f'扫描 {ROOT}')
    print(f'  定义 {len(defined)} 个 token / 引用 {len(used)} 个')
    if not missing:
        print('  [OK] 无幽灵 token')
        return 0

    print(f'  [FAIL] 发现 {len(missing)} 个幽灵 token：')
    for k, fs in sorted(missing.items()):
        print(f'     {k:24} {len(fs)} 处: {", ".join(fs)}')
    return 1 if strict else 0


if __name__ == '__main__':
    raise SystemExit(main())

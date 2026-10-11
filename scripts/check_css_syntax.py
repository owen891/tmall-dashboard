#!/usr/bin/env python
"""CSS 结构门禁：拦截会让浏览器静默丢弃后续规则的语法错误。

用法：
    python scripts/check_css_syntax.py            # 只报告
    python scripts/check_css_syntax.py --strict   # 有问题就退出码 1

为什么要查这个：
    CSS 解析器对语法错误**从不报错**，只会丢弃它无法理解的部分。一次实测事故：
    编辑时用 `.demo-picker__backdrop { ... }` 覆盖掉了 `.demo-period__mode {` 这一行，
    后面的声明体 `display:inline-flex; ... }` 变成没有选择器的孤立声明块。
    浏览器从这里开始把**后续规则一起吞掉** —— 包括 `.demo-picker__backdrop{position:fixed}`，
    导致弹窗以 position:static 渲染在文档流底部（top: 2432px），完全在视口外。
    页面上表现为「点了没反应」，但 console 无报错、异常捕获为空、单元测试全绿。

    这类 bug 靠肉眼 review 和截图都极难发现，必须在提交前做静态结构校验。

判据（先剥离注释与字符串，避免误报）：
    1. 花括号必须配对，且不允许出现负深度（多余的 `}`）
    2. 不允许「深度为 0 处出现 `属性: 值;` 形态」的孤立声明块
    3. 注释与字符串必须闭合
"""
from __future__ import annotations

import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "frontend" / "ui_demo"

# 顶层孤立声明的形态：`--x: v;` 或 `color: red;`（排除伪类、选择器、@规则）
ORPHAN_DECL_RE = re.compile(r"^\s*(?:--[a-z0-9-]+|[a-z-]{2,})\s*:\s*[^;{}]+;", re.IGNORECASE)


def strip_comments_and_strings(source: str) -> tuple[str, list[str]]:
    """把注释与字符串替换为等长空白，保留换行以便定位行号。"""
    problems: list[str] = []
    out: list[str] = []
    i = 0
    length = len(source)
    in_comment = False
    quote: str | None = None
    while i < length:
        char = source[i]
        nxt = source[i + 1] if i + 1 < length else ""
        if in_comment:
            if char == "*" and nxt == "/":
                in_comment = False
                out.append("  ")
                i += 2
                continue
            out.append("\n" if char == "\n" else " ")
            i += 1
            continue
        if quote is not None:
            if char == "\\":
                out.append("  ")
                i += 2
                continue
            if char == quote:
                quote = None
            out.append("\n" if char == "\n" else " ")
            i += 1
            continue
        if char == "/" and nxt == "*":
            in_comment = True
            out.append("  ")
            i += 2
            continue
        if char in ('"', "'"):
            quote = char
            out.append(" ")
            i += 1
            continue
        out.append(char)
        i += 1
    if in_comment:
        problems.append("注释未闭合（缺少 */）")
    if quote is not None:
        problems.append("字符串未闭合（缺少成对引号）")
    return "".join(out), problems


def validate_css_text(source: str, label: str = "<text>") -> list[str]:
    """返回结构错误列表；空列表表示通过。"""
    text, problems = strip_comments_and_strings(source)
    errors: list[str] = list(problems)

    depth = 0
    min_depth = 0
    line = 1
    orphan_line: int | None = None
    orphan_snippet = ""
    i = 0
    length = len(text)
    while i < length:
        char = text[i]
        if char == "\n":
            line += 1
            i += 1
            continue
        if char == "{":
            depth += 1
            i += 1
            continue
        if char == "}":
            depth -= 1
            if depth < min_depth:
                min_depth = depth
            i += 1
            continue
        # 深度 0 处出现声明形态 => 孤立声明块（选择器被误删的典型症状）
        if depth == 0 and orphan_line is None and (char.isalpha() or char == "-"):
            match = ORPHAN_DECL_RE.match(text[i : i + 200])
            if match:
                orphan_line = line
                orphan_snippet = match.group(0).strip()
        i += 1

    if min_depth < 0:
        errors.append(f"多余的右花括号 `}}`（最小深度 {min_depth}）")
    if depth > 0:
        errors.append(f"花括号未闭合（结尾深度 {depth}，缺少 {depth} 个 `}}`）")
    if orphan_line is not None:
        errors.append(
            f"第 {orphan_line} 行存在孤立声明块 `{orphan_snippet}`："
            "它没有选择器，浏览器会丢弃其后的规则。通常是编辑时覆盖了选择器行。"
        )
    return errors


def css_files() -> list[pathlib.Path]:
    return sorted(p for p in UI_ROOT.rglob("*.css") if p.is_file())


def validate_all() -> dict[str, list[str]]:
    """返回 {相对路径: 错误列表}，只包含有问题的文件。"""
    failures: dict[str, list[str]] = {}
    for path in css_files():
        errors = validate_css_text(path.read_text(encoding="utf-8"), path.name)
        if errors:
            failures[path.relative_to(UI_ROOT).as_posix()] = errors
    return failures


def main() -> int:
    # Windows 控制台默认 GBK，输出需降级为 ASCII 安全字符，避免 UnicodeEncodeError。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    strict = "--strict" in sys.argv
    files = css_files()
    failures = validate_all()

    print(f"扫描 {UI_ROOT}")
    print(f"  CSS 文件 {len(files)} 个")
    if not failures:
        print("  [OK] 结构合法：括号配对、无孤立声明块、注释与字符串闭合")
        return 0

    print(f"  [FAIL] {len(failures)} 个文件存在结构错误：")
    for name, errors in sorted(failures.items()):
        print(f"    {name}")
        for error in errors:
            print(f"      - {error}")
    return 1 if strict else 0


if __name__ == "__main__":
    raise SystemExit(main())

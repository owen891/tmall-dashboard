#!/usr/bin/env python
"""事件绑定规范检查：禁止用 class 选择器绑定事件，必须用 data 属性。

用法：
    python scripts/check_event_binding.py            # 只报告
    python scripts/check_event_binding.py --strict   # 有违规就退出码 1

为什么要查这个（DESIGN_SYSTEM.md 第 11 节禁止事项 7）：
    class 是**样式**契约，data 属性是**行为**契约。用 class 选择器绑定事件，
    等于把行为挂在了样式名上。而 BEM 类名清理是 DESIGN_SYSTEM.md 明写的方向，
    一旦有人重命名 class，事件会**静默失效**——不报错、不告警，按钮就是没反应。
    这与 check_css_syntax.py 头部记录的那次事故是同一类失效模式：
    改的人认为自己只动了样式。

判据：
    在同一处代码里同时出现
      (a) querySelector / querySelectorAll 的参数字面量是 `.xxx` 起头的 class 选择器
      (b) 该表达式后面跟着 .addEventListener( 或 .on<事件> =
    则判为违规。

    匹配在**跨行窗口**上进行（默认 6 行）：`forEach((el) => {\n el.addEventListener(...)`
    这种换行写法与单行写法是同一个问题，格式化器的断行不该决定门禁是否命中。

    只认「字面量」：`querySelectorAll(selector)` 这种变量形式不在此列，
    因为静态无法判定其运行时取值——宁可漏报，也不要制造误报把门禁变成噪音。

豁免：
    EXEMPT 里登记的文件 + 理由。组件层（ui-components.js / field-selector.js）
    允许用 class 定位自己刚创建的子节点，因为那是组件内部结构，不跨样式边界。
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent / 'frontend' / 'ui_demo'

# 跨行窗口：class 选择器之后、事件绑定之前允许多少字符（约 3~4 行）
CONNECT_WINDOW = 220

# 登记豁免：key 是相对 ROOT 的 posix 路径，value 是理由。
EXEMPT = {
    'assets/ui-components.js': '组件层：定位自己创建的 ui-* 子节点，属组件内部结构',
    'assets/field-selector.js': '组件层：字段选择器内部结构',
}

# `.class` 起头的选择器字面量（允许后代/子代/属性等组合器）
SELECTOR_RE = re.compile(
    r"""querySelector(?:All)?\s*\(\s*['"`](\.([A-Za-z0-9_-]+)[^'"`]*)['"`]\s*\)""",
    re.VERBOSE,
)
# 事件绑定出现处
BIND_RE = re.compile(r"""\.addEventListener\s*\(|\.on[a-z]+\s*=\s*""", re.VERBOSE)


def _binds_same_chain(text: str, start: int) -> bool:
    """判定从 start 起，选择器结果是否**自身**被绑定了事件。

    真正的违规是「选中 → 绑定到这一批节点」，有三种写法：
        el.addEventListener(...)
        forEach((el) => { el.addEventListener(...) })
        forEach((el) => { const i = ...; el.addEventListener(...) })   // 体内先有分号
    而下面这种只是「选中节点做别的事，附近另有事件绑定」，不是违规：
        card.querySelector('.x')?.firstElementChild?.replaceWith(img);
        ...下一个语句...  cardImage?.addEventListener('error', ...)   // 另一个元素

    划界要点：**先按语句结束（分号）截断，再额外放行一层箭头函数体**。
    只用定长字符窗口会漂到下一个语句上，把无关绑定算成违规
    （lifecycle-live.js / period-review-live.js / market-ranking-live.js 三处误报
    都是这样来的：窗口越过了分号，命中了 cardImage / textarea / window 的监听）。

    实现：从选择器之后截到「第一个不在括号内的分号」为止，只看这一段。
    括号深度用 ( [ { 递增 —— 这样箭头函数体内的分号不会被当成语句结束
    （table-controls.js:458 是 `forEach((button) => { const index = ...;`
    绑定在体内分号之后，必须靠括号深度才能覆盖到）。
    """
    depth = 0
    end = min(len(text), start + CONNECT_WINDOW)
    for i in range(start, end):
        ch = text[i]
        if ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
        elif ch == ';' and depth <= 0:
            end = i
            break
    return bool(BIND_RE.search(text[start:end]))


def scan(root: pathlib.Path):
    hits = []
    for f in sorted(root.rglob('*.js')):
        rel = f.relative_to(root).as_posix()
        if rel in EXEMPT or rel.startswith('vendor/'):
            continue
        if any(rel.endswith(n) for n in ('echarts-5.5.1.min.js', 'echarts-custom.min.js', 'lucide-1.8.0.min.js')):
            continue
        text = f.read_text(encoding='utf-8')
        # 行号表：offset -> 行号
        line_starts = [0]
        for i, ch in enumerate(text):
            if ch == '\n':
                line_starts.append(i + 1)

        def lineno(off: int) -> int:
            lo, hi = 0, len(line_starts) - 1
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if line_starts[mid] <= off:
                    lo = mid
                else:
                    hi = mid - 1
            return lo + 1

        for m in SELECTOR_RE.finditer(text):
            if _binds_same_chain(text, m.end()):
                ln = lineno(m.start())
                snippet = text[line_starts[ln - 1]:text.find('\n', line_starts[ln - 1]) if text.find('\n', line_starts[ln - 1]) != -1 else None]
                hits.append((rel, ln, m.group(2), snippet.strip()))
    return hits


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass
    strict = '--strict' in sys.argv
    hits = scan(ROOT)

    print(f'扫描 {ROOT}')
    if not hits:
        print('  [OK] 无 class 选择器事件绑定')
        return 0

    print(f'  [FAIL] 发现 {len(hits)} 处 class 选择器事件绑定（禁止事项 7）：')
    for rel, lineno, cls, text in hits:
        print(f'     {rel}:{lineno}  .{cls}')
        print(f'       {text[:150]}')
    print('\n  修法：改用 data 属性选择器，例如 [data-action="toggle"]；')
    print('        元素上补对应的 data-* 属性。')
    return 1 if strict else 0


if __name__ == '__main__':
    raise SystemExit(main())

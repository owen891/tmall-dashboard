"""为「文字专用语义色」挑值：按 WCAG 2.1 相对亮度算对比度，要求在所有可能的底色上都 >= 4.5。

用法：
    ./.venv/Scripts/python.exe scripts/pick_text_tokens.py

浅色模式：文字是深色 → 最暗的底色是最坏情况（实测是 brand-tint #eef2ff 与 surface-muted #f3f4f6）。
暗色模式：文字是浅色 → 最亮的底色（--surface-muted）是最坏情况。
**改 tokens.css 里的 --*-text / --color-gray-550 之前先跑这个脚本。**

两组输出：
- 语义色 6 族（brand/success/warning/danger/info/purple）的候选深浅档；
- 中性灰 --text-secondary 的候选档（NEUTRAL_CANDIDATES，对应 --color-gray-550）。
"""

def srgb_to_lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color):
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = ''.join(ch * 2 for ch in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * srgb_to_lin(r) + 0.7152 * srgb_to_lin(g) + 0.0722 * srgb_to_lin(b)


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


LIGHT_BG = {
    'surface-base': '#ffffff',
    'surface-page': '#f5f5f5',
    'surface-muted': '#f3f4f6',
    'surface-selected': '#fcfcfd',
    'brand-tint': '#eef2ff',
    'success-tint': '#ecfdf5',
    'warning-tint': '#fffbeb',
    'danger-tint': '#fef2f2',
    'info-tint': '#eff6ff',
    'purple-tint': '#f5f3ff',
}

DARK_BG = {
    'surface-base': '#171d32',
    'surface-page': '#0f1426',
    'surface-raised': '#1f2740',
    'surface-muted': '#293451',
    'surface-selected': '#1e1b4b',
    'brand-tint': '#1e1b4b',
    'success-tint': '#0c2b24',
    'warning-tint': '#34240a',
    'danger-tint': '#35131a',
    'info-tint': '#142747',
    'purple-tint': '#271d43',
}

# 当前值（要诊断的对象）+ 候选替换值。顺序 = 偏好顺序（越靠前越接近原色）。
CANDIDATES = {
    'light': {
        'brand':   ['#6366f1', '#4f46e5', '#4338ca', '#3730a3'],
        'success': ['#10b981', '#047857', '#15803d', '#065f46'],
        'warning': ['#f59e0b', '#b45309', '#92400e', '#78350f'],
        'danger':  ['#ef4444', '#dc2626', '#b91c1c', '#991b1b'],
        'info':    ['#3b82f6', '#2563eb', '#1d4ed8', '#1e40af'],
        'purple':  ['#8b5cf6', '#7c3aed', '#6d28d9', '#5b21b6'],
    },
    'dark': {
        'brand':   ['#818cf8', '#a5b4fc', '#c7d2fe'],
        'success': ['#10b981', '#34d399', '#6ee7b7'],
        'warning': ['#f59e0b', '#fbbf24', '#fcd34d'],
        'danger':  ['#ef4444', '#f87171', '#fca5a5'],
        'info':    ['#3b82f6', '#60a5fa', '#93c5fd'],
        'purple':  ['#8b5cf6', '#a78bfa', '#c4b5fd'],
    },
}

# 中性文字色：--text-secondary 原值 = --color-gray-500 #6b7280。
# 在白底 4.83 达标，但底色变成 --surface-muted #f3f4f6（4.39）或 brand-tint #eef2ff（4.32）就不够。
# 2026-10-01 因此新增一档 --color-gray-550，专门给 --text-secondary 用。
NEUTRAL_CANDIDATES = {
    'light': ['#6b7280', '#68707d', '#646c79', '#5f6875', '#4b5563'],
    'dark': ['#cbd5e1'],
}

TARGET = 4.5
for mode, table in (('light', LIGHT_BG), ('dark', DARK_BG)):
    print(f'\n================ {mode} 模式（要求 >= {TARGET}）================')
    groups = [(k, v) for k, v in CANDIDATES[mode].items()] + [('neutral(--text-secondary)', NEUTRAL_CANDIDATES[mode])]
    for token, colors in groups:
        print(f'\n-- {token} --')
        for color in colors:
            worst = min((contrast(color, bg), name) for name, bg in table.items())
            ok = '✅' if worst[0] >= TARGET else '❌'
            allc = ', '.join(f'{n}={contrast(color, bg):.2f}' for n, bg in table.items())
            print(f'  {ok} {color}  最差 {worst[0]:.2f} @ {worst[1]:<16} | {allc}')

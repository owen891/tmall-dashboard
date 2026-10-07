# -*- coding: utf-8 -*-
"""把月度复盘沉淀的「核心单品九维完整分析」页转换成 tmall-dashboard 应用页面。

来源（默认）：E:\\skill-dianshang\\月复盘SKILL\\核心单品九维分析\\核心单品九维完整分析.html
  —— 每月复盘后用 .tmp_gen_html.py 生成的那份（内容经人工核准）。
产物：
  frontend/ui_demo/pages/core-product-analysis.html   应用壳子 + 九维内容（类名不变）
  frontend/ui_demo/assets/core-product-analysis-live.js  周度趋势图表初始化（token 配色）

设计：内容是**月度静态精选**（含人工结论），不做活数据查询；配色统一走
assets/themes/core-product-domain.css 映射到 tokens.css。换月重新生成九维页后
重跑本脚本即可。
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES_DIR = os.path.join(APP_ROOT, 'frontend', 'ui_demo', 'pages')
ASSETS_DIR = os.path.join(APP_ROOT, 'frontend', 'ui_demo', 'assets')
DEFAULT_SOURCE = r'E:\skill-dianshang\月复盘SKILL\核心单品九维分析\核心单品九维完整分析.html'

PAGE_VERSION = '20261007a'

HEAD_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>核心单品九维分析 | 天猫数据仪表盘</title>
  <link rel="stylesheet" href="../assets/tokens.css?v={v}">
  <link rel="stylesheet" href="../assets/shell.css?v={v}">
  <link rel="stylesheet" href="../assets/components.css?v={v}">
  <link rel="stylesheet" href="../assets/themes/core-product-domain.css?v={v}">
  <script src="../assets/echarts-custom.min.js?v={v}"></script>
  <script src="../assets/lucide-custom.min.js?v={v}"></script>
</head>
<body data-page="core-product-analysis">
  <div class="demo-app">
    <aside class="demo-sidebar" data-shell-sidebar></aside>
    <div class="demo-main">
      <header class="demo-topbar" data-shell-header></header>
      <main class="demo-page">
        <div style="margin-bottom:var(--space-2);font-size:var(--font-size-meta);color:var(--text-secondary)">商品经营 / 核心单品九维分析</div>
        <header style="margin-bottom:var(--space-4)">
          <h1 style="font-size:var(--font-size-title);font-weight:700;color:var(--text-primary)">核心单品九维分析<span style="color:var(--brand)">（2026年9月）</span></h1>
          <p style="font-size:var(--font-size-secondary);color:var(--text-secondary);margin-top:4px">{subtitle}</p>
        </header>
        <div class="ninedim">
"""

FOOT_TEMPLATE = """
        </div>
      </main>
    </div>
  </div>
  <script src="../assets/api.js?v={v}"></script>
  <script src="../assets/navigation.js?v={v}"></script>
  <script src="../assets/labels.js?v={v}"></script>
  <script src="../assets/shell.js?v={v}"></script>
  <script src="../assets/format.js?v={v}"></script>
  <script src="../assets/ui-components.js?v={v}"></script>
  <script src="../assets/core-product-analysis-live.js?v={v}"></script>
</body>
</html>
"""

LIVE_JS = """// 核心单品九维分析：静态精选内容（月度复盘沉淀，人工核准），本文件只负责周度趋势图表。
// 数据口径见页面头说明；后续如需活数据化，逐维接 /api/products/<id>/detail|trade|promotion。
(function () {
  function initCharts() {
    document.querySelectorAll('.ninedim .chart').forEach(function (el) {
      if (typeof echarts === 'undefined') {
        el.textContent = '周度趋势图暂不可用（图表库加载失败）';
        el.style.display = 'flex';
        el.style.alignItems = 'center';
        el.style.justifyContent = 'center';
        el.style.color = 'var(--text-tertiary)';
        el.style.fontSize = '12px';
        return;
      }
      var gsv = JSON.parse(el.dataset.gsv || '[]');
      var prof = JSON.parse(el.dataset.prof || '[]');
      var labels = JSON.parse(el.dataset.labels || '["W1","W2","W3","W4","W5"]');
      var c = echarts.init(el);
      c.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['GSV(万)', '利润(万)'], top: 0, textStyle: { fontSize: 11 } },
        grid: { left: 40, right: 16, top: 28, bottom: 24 },
        xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
        yAxis: { type: 'value', axisLabel: { fontSize: 11 } },
        series: [
          { name: 'GSV(万)', type: 'bar', data: gsv, itemStyle: { color: '#4f46e5' }, barWidth: '45%' },
          { name: '利润(万)', type: 'line', data: prof, itemStyle: { color: '#ef4444' }, lineStyle: { width: 2 } }
        ]
      });
      window.addEventListener('resize', function () { c.resize(); });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initCharts);
  else initCharts();
})();
"""


def extract(source_html):
    """取 .nav（商品锚点）、.wrap（正文）、topbar 副标题（口径行）。"""
    m_nav = re.search(r'(<div class="nav">.*?</div>)\s*<div class="wrap">', source_html, re.S)
    m_wrap = re.search(r'<div class="wrap">(.*?)<div class="footer">', source_html, re.S)
    m_sub = re.search(r'<div class="topbar">.*?<div class="sub">(.*?)</div>', source_html, re.S)
    missing = [n for n, m in (('nav', m_nav), ('wrap', m_wrap), ('sub', m_sub)) if not m]
    if missing:
        raise SystemExit(f'源页面结构不符，缺 {missing} —— 九维页模板可能变了，请检查')
    nav, wrap, sub = m_nav.group(1), m_wrap.group(1), m_sub.group(1)
    # 内容里不允许再带独立页的 <script>（图表初始化已移植 live.js）
    assert '<script' not in wrap, 'wrap 内容含 script，请人工检查'
    return nav.strip(), wrap.strip(), sub.strip()


def localize_images(wrap, source_dir):
    """主图是源页面相对路径 assets/<pid>.jpg：拷进应用 assets 并改写为 ../assets/pages/…。"""
    import shutil
    dest_dir = os.path.join(ASSETS_DIR, 'pages', 'core-product-analysis')
    os.makedirs(dest_dir, exist_ok=True)
    srcs = sorted(set(re.findall(r'src="(assets/[^"]+\.jpg)"', wrap)))
    for rel in srcs:
        src_file = os.path.join(source_dir, rel.replace('/', os.sep))
        if os.path.isfile(src_file):
            shutil.copy2(src_file, os.path.join(dest_dir, os.path.basename(rel)))
        else:
            print(f'  ⚠️ 图片缺失，跳过: {src_file}')
    wrap = re.sub(r'src="assets/([^"]+\.jpg)"', r'src="../assets/pages/core-product-analysis/\1"', wrap)
    print(f'  主图本地化: {len(srcs)} 张 → {dest_dir}')
    return wrap


def main():
    source = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SOURCE
    source_dir = os.path.dirname(os.path.abspath(source))
    with open(source, encoding='utf-8') as f:
        html = f.read()
    nav, wrap, sub = extract(html)
    wrap = localize_images(wrap, source_dir)

    page = (HEAD_TEMPLATE.format(v=PAGE_VERSION, subtitle=sub)
            + nav + '\n' + wrap + FOOT_TEMPLATE.format(v=PAGE_VERSION))
    page_path = os.path.join(PAGES_DIR, 'core-product-analysis.html')
    with open(page_path, 'w', encoding='utf-8', newline='') as f:
        f.write(page)

    live_path = os.path.join(ASSETS_DIR, 'core-product-analysis-live.js')
    with open(live_path, 'w', encoding='utf-8', newline='') as f:
        f.write(LIVE_JS)

    products = len(re.findall(r'<section', wrap))
    print(f'✅ 页面已生成: {page_path} ({len(page)/1024:.0f}KB, {products} 个单品 section)')
    print(f'✅ 图表脚本已生成: {live_path}')
    print('提醒：新页面还需在 application_pages / page_capability_service / shell.js 注册（如尚未注册）')


if __name__ == '__main__':
    main()

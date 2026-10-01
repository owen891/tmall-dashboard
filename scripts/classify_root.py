# 根目录散落脚本的三重证据分类（只读，不移动任何文件）。
#
# 证据强度（有任一即保留）：
#   硬：被 package.json scripts 引用（词边界）
#   硬：被其它文件 import / require / subprocess 调用（正则扫全项目，排除自指目录）
#   硬：文件名出现在 .py/.ps1/.bat 的 subprocess / os.system 调用里
#   弱：文档提及 —— 必须读上下文，出现「不要运行/已弃用/已迁移/历史」等措辞就不算
#   人工：含 Usage: / 用法： 文档头，或含 export 语句
#
# 陷阱（照抄 skill）：
#   - 排除自指目录（docs/、.workbuddy-ai/memory/、.tmp/、archive/、legacy/），否则判据全废
#   - Windows 下 Path 返回反斜杠，startswith('docs/') 恒 False → 必须先归一化
import json
import re
import subprocess
from pathlib import Path

ROOT = Path('.').resolve()
SKIP_DIRS = {
    'node_modules', '.git', '.venv', '__pycache__', 'archive', 'legacy', 'docs',
    '.tmp', '.workbuddy-ai', 'desktop', 'frontend-build', '.xmind_extract',
    'data', 'logs', 'instance', 'models', 'repos', 'packaging',
}
SCAN_EXT = {'.py', '.js', '.cjs', '.mjs', '.ps1', '.bat', '.cmd', '.json', '.yaml', '.yml', '.md', '.txt', '.html'}

# 候选 = 根目录里以下划线开头的散落文件 + 明显的日志/一次性产物
root_files = [p for p in ROOT.iterdir() if p.is_file()]
candidates = [p for p in root_files if p.name.startswith('_')]
candidates += [p for p in root_files if p.name in {
    'app_stderr.log', 'app_stdout.log', 'combos_36470_36478.json',
    'pelican-bicycle.html', 'pelican-bike-animation.html',
}]
candidates = sorted(set(candidates), key=lambda p: p.name)

# ---- 收集「全项目正文」（排除自指目录）----
corpus = []
for path in ROOT.rglob('*'):
    if not path.is_file():
        continue
    rel = path.relative_to(ROOT).as_posix()
    if any(rel == d or rel.startswith(d + '/') for d in SKIP_DIRS):
        continue
    if path.suffix.lower() not in SCAN_EXT:
        continue
    if path in candidates:
        continue  # 不拿候选文件互相引用当证据（同批探针常互相 import，但那不代表有人用）
    try:
        corpus.append((rel, path.read_text(encoding='utf-8', errors='ignore')))
    except OSError:
        pass

# package.json 的 scripts 单独取出（词边界匹配）
pkg = ROOT / 'package.json'
pkg_text = pkg.read_text(encoding='utf-8') if pkg.exists() else ''

DEPRECATED_HINTS = ('不要运行', '已弃用', '已废弃', '已迁移', '已完成', '历史', '旧版', '遗留', 'deprecated')


def wb_pattern(name):
    return re.compile(r'(?<![\w.-])' + re.escape(name) + r'(?![\w.-])')


report = []
for cand in candidates:
    name = cand.name
    hits = {'pkg': [], 'code': [], 'doc': [], 'usage_header': False, 'has_export': False}
    if pkg_text and wb_pattern(name).search(pkg_text):
        hits['pkg'].append('package.json')
    for rel, text in corpus:
        if not wb_pattern(name).search(text):
            continue
        if rel.endswith(('.md', '.txt')):
            # 文档提及：看命中行的上下文有没有「已弃用」措辞
            for line in text.splitlines():
                if wb_pattern(name).search(line):
                    if any(h in line for h in DEPRECATED_HINTS):
                        hits.setdefault('doc_deprecated', []).append(f'{rel}: {line.strip()[:90]}')
                    else:
                        hits['doc'].append(f'{rel}: {line.strip()[:90]}')
                    break
        else:
            hits['code'].append(rel)
    try:
        head = cand.read_text(encoding='utf-8', errors='ignore')[:1500]
        hits['usage_header'] = bool(re.search(r'(Usage:|用法：|用法:)', head))
        hits['has_export'] = bool(re.search(r'^\s*export\s', head, re.M))
    except OSError:
        pass
    # 判定
    strong = bool(hits['pkg'] or hits['code'])
    report.append({
        'file': name, 'bytes': cand.stat().st_size,
        'verdict': 'KEEP' if strong else ('REVIEW' if (hits['usage_header'] or hits['has_export'] or hits['doc']) else 'ARCHIVE'),
        'evidence': hits,
    })

out = Path('.tmp/root-classification.json')
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

keep = [r for r in report if r['verdict'] == 'KEEP']
review = [r for r in report if r['verdict'] == 'REVIEW']
arch = [r for r in report if r['verdict'] == 'ARCHIVE']
print(f'候选 {len(report)} 个 → KEEP {len(keep)} / REVIEW {len(review)} / ARCHIVE {len(arch)}\n')
for r in report:
    ev = []
    if r['evidence']['pkg']:
        ev.append('pkg')
    if r['evidence']['code']:
        ev.append('code:' + ','.join(r['evidence']['code'][:3]))
    if r['evidence']['usage_header']:
        ev.append('Usage头')
    if r['evidence']['has_export']:
        ev.append('export')
    if r['evidence']['doc']:
        ev.append('doc:' + str(len(r['evidence']['doc'])))
    if r['evidence'].get('doc_deprecated'):
        ev.append('doc(已弃用措辞):' + str(len(r['evidence']['doc_deprecated'])))
    print(f"  {r['verdict']:<8} {r['file']:<26} {r['bytes']:>8}B  {', '.join(ev) or '无任何证据'}")

print('\n--- REVIEW 明细（需人工看用途）---')
for r in review:
    print(f"  {r['file']}")
    for k in ('usage_header', 'has_export'):
        if r['evidence'][k]:
            print(f'      {k}=True')
    for d in r['evidence']['doc'][:3]:
        print(f'      doc: {d}')
    for d in r['evidence'].get('doc_deprecated', [])[:2]:
        print(f'      doc(已弃用): {d}')
print(f'\n报告已写 .tmp/root-classification.json')

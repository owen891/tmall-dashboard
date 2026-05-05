import sqlite3
import urllib.request
import json
import os
import re
from datetime import datetime

print("=" * 60)
print("海贝海系统全面检查报告")
print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

issues = []

# ============================================
# 1. 数据库检查
# ============================================
print("\n【1. 数据库检查】")
db_path = 'f:/ai/.accelerate/tmall-dashboard/backend/data/db/dashboard.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1.1 列出所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [row[0] for row in cursor.fetchall()]
print(f"\n✓ 数据库表: {len(tables)}个")
for t in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {t}")
    count = cursor.fetchone()[0]
    print(f"  - {t}: {count}条记录")
    if count == 0:
        issues.append(f"⚠ 表 {t} 为空")

# 1.2 检查核心数据表结构
for table in ['weekly_data', 'daily_data', 'monthly_data', 'products']:
    if table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        cols = [row[1] for row in cursor.fetchall()]
        print(f"\n✓ {table} 表字段({len(cols)}个): {', '.join(cols[:10])}...")
        
        # 检查负数
        for col in ['payment_amount', 'visitors', 'ad_spend']:
            if col in cols:
                cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} < 0")
                neg_count = cursor.fetchone()[0]
                if neg_count > 0:
                    issues.append(f"⚠ {table}.{col} 有{neg_count}条负数记录")

# 1.3 检查数据周期分布
print("\n【数据周期分布】")
for table, date_col in [('weekly_data', 'week_start'), ('daily_data', 'date'), ('monthly_data', 'month')]:
    if table in tables:
        cursor.execute(f"SELECT COUNT(DISTINCT {date_col}) FROM {table}")
        period_count = cursor.fetchone()[0]
        cursor.execute(f"SELECT MIN({date_col}), MAX({date_col}) FROM {table}")
        min_max = cursor.fetchone()
        print(f"  {table}: {period_count}个周期, 范围: {min_max[0]} ~ {min_max[1]}")

conn.close()

# ============================================
# 2. 后端API检查
# ============================================
print("\n【2. 后端API检查】")
base_url = "http://localhost:8000/api"

api_endpoints = [
    ("KPI数据", "/kpi?dim=weekly"),
    ("KPI Summary", "/kpi/summary?dimension=weekly"),
    ("Dashboard", "/dashboard"),
    ("Dashboard Summary", "/dashboard/summary"),
    ("Top Products", "/dashboard/top-products?dimension=weekly"),
    ("产品列表", "/products"),
    ("健康度", "/health/list"),
    ("趋势", "/trends"),
    ("广告", "/ads/summary"),
    ("利润", "/profit/summary"),
]

def check_api(url, timeout=5):
    """Helper function to check API using urllib"""
    try:
        response = urllib.request.urlopen(url, timeout=timeout)
        status_code = response.getcode()
        data = json.loads(response.read().decode())
        return status_code, data
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        raise e

for name, endpoint in api_endpoints:
    try:
        status_code, data = check_api(f"{base_url}{endpoint}")
        if status_code == 200:
            if data.get('code') == 200:
                print(f"  ✓ {name}: 正常")
            else:
                print(f"  ✗ {name}: 返回码{data.get('code')}")
                issues.append(f"✗ {name} API返回错误: {data.get('message')}")
        else:
            print(f"  ✗ {name}: HTTP {status_code}")
            issues.append(f"✗ {name} API HTTP错误: {status_code}")
    except Exception as e:
        print(f"  ✗ {name}: {str(e)[:50]}")
        issues.append(f"✗ {name} API异常: {str(e)}")

# ============================================
# 3. KPI数据合理性检查
# ============================================
print("\n【3. KPI数据合理性检查】")
try:
    status_code, resp_data = check_api(f"{base_url}/kpi?dim=weekly")
    if status_code == 200:
        kpi_data = resp_data['data']['kpi']
        
        gmv = kpi_data.get('total_gmv', {}).get('value', 0)
        visitors = kpi_data.get('visitors', {}).get('value', 0)
        conversion = kpi_data.get('conversion', {}).get('value', 0)
        roi = kpi_data.get('roi', {}).get('value', 0)
        ad_spend = kpi_data.get('ad_spend', {}).get('value', 0)
        
        print(f"  GMV: ¥{gmv:,.2f}")
        print(f"  访客数: {visitors:,}")
        print(f"  转化率: {conversion}%")
        print(f"  ROI: {roi}")
        print(f"  广告支出: ¥{ad_spend:,.2f}")
        
        if gmv <= 0:
            issues.append("✗ GMV为负数或0")
        if visitors <= 0:
            issues.append("✗ 访客数为负数或0")
        if conversion < 0 or conversion > 100:
            issues.append(f"✗ 转化率异常: {conversion}%")
        if roi < 0:
            issues.append("✗ ROI为负数")
            
        # 检查环比变化是否合理
        gmv_pct = kpi_data.get('total_gmv', {}).get('percent', 0)
        if abs(gmv_pct) > 100:
            issues.append(f"⚠ GMV环比变化过大: {gmv_pct}%")
            
except Exception as e:
    print(f"  ✗ 无法获取KPI数据: {e}")
    issues.append(f"✗ KPI数据检查失败: {e}")

# ============================================
# 4. 前端文件检查
# ============================================
print("\n【4. 前端文件检查】")
import os
frontend_src = 'f:/ai/.accelerate/tmall-dashboard/frontend/src'

# 检查Dashboard.vue
dashboard_file = f"{frontend_src}/views/Dashboard.vue"
if os.path.exists(dashboard_file):
    with open(dashboard_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查import是否都存在
    import_lines = [line.strip() for line in content.split('\n') if line.strip().startswith('import ')]
    print(f"  Dashboard.vue 导入: {len(import_lines)}个")
    
    # 检查是否有TODO或FIXME
    todo_count = content.count('TODO') + content.count('FIXME')
    if todo_count > 0:
        issues.append(f"⚠ Dashboard.vue 有{todo_count}个TODO/FIXME")
    
    # 检查文件大小
    file_size = len(content)
    print(f"  Dashboard.vue 大小: {file_size/1000:.1f}KB ({content.count(chr(10))}行)")
    
    if file_size > 30000:
        issues.append("⚠ Dashboard.vue 文件过大，建议拆分")

# 检查其他视图文件
views_dir = f"{frontend_src}/views"
if os.path.exists(views_dir):
    view_files = [f for f in os.listdir(views_dir) if f.endswith('.vue')]
    print(f"  视图文件: {len(view_files)}个")
    
    # 检查路由中定义的视图是否都存在
    router_file = f"{frontend_src}/router/index.js"
    if os.path.exists(router_file):
        with open(router_file, 'r', encoding='utf-8') as f:
            router_content = f.read()
        
        import re
        route_components = re.findall(r"@/views/(\w+)\.vue", router_content)
        missing_views = [v for v in route_components if f"{v}.vue" not in view_files]
        
        if missing_views:
            print(f"  ✗ 缺失视图: {missing_views}")
            issues.append(f"✗ 路由引用了不存在的视图: {', '.join(missing_views)}")
        else:
            print(f"  ✓ 所有路由视图都存在")

# ============================================
# 5. 依赖检查
# ============================================
print("\n【5. 后端依赖检查】")
try:
    with open('f:/ai/.accelerate/tmall-dashboard/backend/requirements.txt', 'r') as f:
        deps = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    print(f"  依赖包: {len(deps)}个")
except:
    issues.append("✗ 找不到requirements.txt")

# ============================================
# 总结
# ============================================
print("\n" + "=" * 60)
print("检查总结")
print("=" * 60)

if issues:
    print(f"\n共发现 {len(issues)} 个问题:\n")
    for i, issue in enumerate(issues, 1):
        print(f"{i}. {issue}")
else:
    print("\n✓ 未发现明显问题")

print("\n" + "=" * 60)

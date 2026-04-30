import re
import pandas as pd

def clean_percentage(val):
    """百分比字符串转小数: '5.6%' -> 0.056"""
    if pd.isna(val):
        return 0
    if isinstance(val, (int, float)):
        return float(val) / 100 if val > 1 else float(val)
    val = str(val).strip().replace('%', '')
    try:
        result = float(val)
        return result / 100 if result > 1 else result
    except ValueError:
        return 0

def clean_number(val):
    """数字字符串转浮点: '12,345.67' -> 12345.67"""
    if pd.isna(val):
        return 0
    if isinstance(val, (int, float)):
        return float(val)
    val = str(val).strip().replace(',', '').replace('，', '')
    try:
        return float(val)
    except ValueError:
        return 0

def clean_int(val):
    """数字字符串转整数"""
    return int(clean_number(val))

def clean_month(val):
    """月份格式标准化: '26年-3月' -> '2026-03'"""
    if pd.isna(val):
        return None
    val = str(val).strip()
    m = re.match(r"(\d{2})年[-/]?(\d{1,2})月?", val)
    if m:
        year = int(m.group(1))
        month = int(m.group(2))
        return f"20{year:02d}-{month:02d}"
    return val

def parse_date_range(val):
    """日期范围解析: '20260413至20260419' -> ('2026-04-13', '2026-04-19')"""
    if pd.isna(val):
        return None
    val = str(val).strip()
    parts = re.split(r'至|~|—|-', val)
    if len(parts) == 2:
        def fmt(d):
            d = d.strip()
            if len(d) == 8:
                return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
            return d
        return (fmt(parts[0]), fmt(parts[1]))
    return None

def is_valid_row(row, id_col='商品ID'):
    """检查是否为有效数据行（非全零、非表头重复）"""
    if id_col in row and pd.notna(row[id_col]):
        id_val = str(row[id_col]).strip()
        if id_val == '' or id_val.startswith('[') or id_val == id_col:
            return False
        return True
    return False

def classify_action(text):
    """运营动作自动分类"""
    if pd.isna(text) or str(text).strip() == '':
        return None, None
    text = str(text).strip()
    if any(k in text for k in ['付费', '推广']):
        return '加付费' if any(k in text for k in ['加', '增', '提']) else '减付费', text
    if any(k in text for k in ['图', '视频', '详情', '主图']):
        return '换图/内容', text
    if any(k in text for k in ['价', '优惠券', '折扣']):
        return '调价/促销', text
    if any(k in text for k in ['观察', '看', '分析']):
        return '观察分析', text
    return '其他', text

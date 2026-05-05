"""
预览压缩包内容
"""
import zipfile
import os

DATA_DIR = r"F:\bi\海贝海\原始数据"

zip_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.zip')]
print(f"发现 {len(zip_files)} 个ZIP文件\n")

for filename in sorted(zip_files)[:5]:  # 只预览前5个
    filepath = os.path.join(DATA_DIR, filename)
    try:
        with zipfile.ZipFile(filepath, 'r') as z:
            files = z.namelist()
            print(f"📦 {filename}:")
            for f in files[:5]:
                print(f"  - {f}")
            if len(files) > 5:
                print(f"  ... 共 {len(files)} 个文件")
            print()
    except Exception as e:
        print(f"✗ {filename}: {e}\n")

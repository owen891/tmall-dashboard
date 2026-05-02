from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1920, 'height': 1080})
    
    # 访问智能导入页面
    print("正在访问智能导入页面...")
    page.goto('http://localhost:5173/smart-import')
    page.wait_for_load_state('networkidle')
    
    # 等待页面加载
    time.sleep(3)
    
    # 截图
    page.screenshot(path='/workspace/preview.png', full_page=True)
    print("截图已保存到 /workspace/preview.png")
    
    browser.close()

"""常驻启动看板开发服务（默认 127.0.0.1:5000）。

用途：给 WorkBuddy / 计划任务等场景提供一个稳定的、不被调用方回收的启动入口。
直接 ``python app.py`` 在部分工具链下会随父进程结束被回收；本脚本把输出落到
``logs/dev-server.log`` 并以前台阻塞方式运行 Flask 开发服务器。

用法：
    .venv\\Scripts\\python.exe scripts\\start_dev_server.py
"""

import os
import runpy
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(PROJECT_ROOT, 'logs', 'dev-server.log')
APP_PATH = os.path.join(PROJECT_ROOT, 'app.py')


def main():
    os.chdir(PROJECT_ROOT)
    # ``runpy.run_path`` 不会把脚本所在目录加入 ``sys.path``（只有直接
    # ``python app.py`` 才会），缺这一步会让 app.py 里的 `import db` 失败。
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    log = open(LOG_PATH, 'a', encoding='utf-8', buffering=1)
    stamp = datetime.now().isoformat(timespec='seconds')
    print('\n===== start %s pid=%s =====' % (stamp, os.getpid()), file=log)
    sys.stdout = log
    sys.stderr = log
    sys.argv = [APP_PATH]
    runpy.run_path(APP_PATH, run_name='__main__')
    return 0


if __name__ == '__main__':
    sys.exit(main())

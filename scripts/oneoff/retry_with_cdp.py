"""直接调用 start_retry，确保 TMALL_CDP_PORT=9223 传给子进程。"""
import os
import sys
import time

os.environ['TMALL_CDP_PORT'] = '9223'
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 确保项目根在 sys.path
sys.path.insert(0, r'E:\www\tmall-dashboard')

from services.collector_retry_service import start_retry, retry_diff
from services.collector_run_service import get_run, list_checkpoints

parent_run_id = 'b3f15e208f0d4d35b32cd4cff1af864c'
COLLECTORS_DIR = r'E:\www\BI采集\collectors'
VENV_PYTHON = r'E:\www\tmall-dashboard\.venv\Scripts\python.exe'
SCRIPT_NAME = 'collect_sycm_item_flow_v6.py'

result = start_retry(
    parent_run_id,
    collectors_dir=COLLECTORS_DIR,
    python_executable=VENV_PYTHON,
    script_name=SCRIPT_NAME,
    execute=True,
)
child_id = result['child_run_id']
print('child_run_id:', child_id)
print('planned units:', result['unit_count'])

# Poll
for i in range(60):
    time.sleep(5)
    run = get_run(child_id)
    st = run['status']
    ckpts = list_checkpoints(child_id)
    print(f'[{i*5}s] status={st}  checkpoints={len(ckpts)}')
    if st in ('succeeded', 'failed'):
        print()
        print('=== final run ===')
        print('status:', run['status'])
        print('error_code:', run.get('error_code'))
        print('error_message:', (run.get('error_message') or '')[-800:])
        print('stats:', run.get('stats_json'))
        print()
        print('=== checkpoints ===')
        for c in ckpts:
            print(f"  {c['unit_type']}:{c['unit_key']}  {c['status']}  rows={c['row_count']}  err={c.get('last_error_message')}")
        # retry diff
        print()
        print('=== retry_diff ===')
        diff = retry_diff(parent_run_id, child_id)
        print(diff)
        break

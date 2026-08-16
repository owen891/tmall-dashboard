"""Windows Task Scheduler entrypoint for local import scanning."""

import argparse
import os
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run due local import scan jobs')
    parser.add_argument('--once', action='store_true', help='run due jobs once and exit')
    parser.add_argument('--job-id', type=int, help='run one job once')
    args = parser.parse_args(argv)
    if not args.once and args.job_id is None:
        parser.error('--once or --job-id is required')
    from app import create_app
    from services.import_scan_service import ImportScanService
    app = create_app()
    with app.app_context():
        if args.job_id is not None:
            result = [ImportScanService.run_job_once(args.job_id)]
        else:
            result = ImportScanService.run_due_jobs()
        for item in result:
            print(item)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Explicit tier split; unknown tests stay selected, any skip fails the gate."""
import json
import os
import shutil
import sys
from pathlib import Path
import pytest

_skips = []
_allowed_skips = []


def allowed_existing_skip(nodeid, reason):
    manifest = json.loads(Path(__file__).with_name('quality_gates.json').read_text())
    for entry in manifest.get('existing_skip_allowlist', []):
        if entry['nodeid'] != nodeid or entry['reason'] != reason:
            continue
        if entry['condition'] == 'non_windows_or_missing_powershell':
            return sys.platform != 'win32' or shutil.which('powershell.exe') is None
        if entry['condition'] == 'external_sycm_source_missing':
            return not Path(os.environ.get(
                'TMALL_SYCM_ITEM_FLOW_COLLECTOR',
                str(Path(__file__).resolve().parents[1] / 'collectors' / 'collect_sycm_item_flow_v6.py'),
            )).is_file()
    return False


def record_skip(report):
    # pytest's concrete skip representation is (file, line, "Skipped: reason").
    reason = report.longrepr[2] if isinstance(report.longrepr, tuple) else str(report.longrepr)
    if reason.startswith('Skipped: '):
        reason = reason[len('Skipped: '):]
    entry = {'nodeid': report.nodeid, 'reason': reason}
    (_allowed_skips if allowed_existing_skip(report.nodeid, reason) else _skips).append(entry)


def pytest_collection_modifyitems(config, items):
    manifest = json.loads(Path(__file__).with_name('quality_gates.json').read_text())
    browser = set(manifest['browser_pytest_nodes'])
    if os.environ.get('TMALL_GATE_PYTEST_PHASE') == 'browser':
        if {item.nodeid for item in items} != browser:
            raise pytest.UsageError('browser pytest selection does not match manifest')
        return
    excluded = [item for item in items if item.nodeid in browser]
    if {item.nodeid for item in excluded} != browser:
        raise pytest.UsageError('browser test node is missing or renamed; update gate manifest')
    items[:] = [item for item in items if item.nodeid not in browser]
    config.hook.pytest_deselected(items=excluded)


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item, nextitem):
    """Close sqlite handles left behind by a test before the next one runs.

    The gate runs with ``-W error::ResourceWarning``. sqlite3 connections that
    a test forgets to close are finalized by the GC at an arbitrary later
    moment — often while an unrelated test is running — and pytest turns that
    finalizer warning into a failure attributed to the wrong test. Draining
    them at the teardown boundary keeps the attribution honest and prevents
    cross-test contamination.
    """
    import gc
    import sqlite3
    for obj in gc.get_objects():
        if isinstance(obj, sqlite3.Connection):
            try:
                obj.close()
            except sqlite3.ProgrammingError:
                pass
    gc.collect()


def pytest_runtest_logreport(report):
    if report.skipped:
        record_skip(report)


def pytest_collectreport(report):
    if report.skipped:
        record_skip(report)


def pytest_sessionfinish(session, exitstatus):
    reporter = session.config.pluginmanager.get_plugin('terminalreporter')
    if _allowed_skips and reporter:
        reporter.write_line('EXISTING_PLATFORM_EXTERNAL_NOT_VERIFIED: ' + json.dumps(_allowed_skips, ensure_ascii=False))
    if _skips:
        if reporter:
            reporter.write_line('GATE_SKIP_FORBIDDEN: ' + json.dumps(_skips, ensure_ascii=False), red=True)
        session.exitstatus = 1

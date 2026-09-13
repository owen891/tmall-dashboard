"""Compatibility CLI for the retired smart-selection import commands.

The old commands remain available for existing operators, but their writes now
go through the canonical preview/quality/batch/provenance pipeline.
"""

from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from services.import_service import ImportService, ImportValidationError, import_service


def _date_from_filename(filename):
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', os.path.basename(filename))
    return f'{match.group(1)}-{match.group(2)}-{match.group(3)}' if match else None


def _normalise_workbook(content, filename):
    """Add the filename date when legacy exports omit a date column."""
    stat_date = _date_from_filename(filename)
    if not stat_date:
        raise ImportValidationError(f'无法从文件名提取日期：{filename}')

    source = pd.ExcelFile(io.BytesIO(content))
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for index, sheet_name in enumerate(source.sheet_names):
            frame = pd.read_excel(source, sheet_name=sheet_name, header=None, dtype=object)
            frame = ImportService._drop_summary_rows(ImportService._promote_header(frame))
            columns = [str(column).strip() for column in frame.columns]
            if 'date' not in ImportService._mapping(columns):
                frame.insert(0, 'date', stat_date)
            safe_sheet_name = (str(sheet_name).strip() or f'Sheet{index + 1}')[:31]
            frame.to_excel(writer, index=False, sheet_name=safe_sheet_name)
    return output.getvalue()


def run_legacy_import(paths, source_type):
    paths = [os.fspath(path) for path in paths]
    if not paths:
        print(f'Usage: python import_{"smart_daily" if source_type == "product_day" else "smart"}.py <file1.xlsx> [file2.xlsx ...]')
        return 2

    app = create_app()
    imported = 0
    failures = []
    with app.app_context():
        for path in paths:
            if not os.path.isfile(path):
                failures.append(f'{path}: 文件不存在')
                continue
            filename = os.path.basename(path)
            try:
                payload = _normalise_workbook(Path(path).read_bytes(), filename)
                preview = import_service.preview(filename, payload, source_type)
                problems = []
                if preview.get('required_unmapped'):
                    problems.append(f"缺少必填映射：{'、'.join(preview['required_unmapped'])}")
                if preview.get('invalid_rows'):
                    problems.append(f"{preview['invalid_rows']} 行质量异常")
                if preview.get('duplicate_keys'):
                    problems.append(f"{preview['duplicate_keys']} 个重复业务键")
                if problems:
                    # The retired CLI has no preview-id retry workflow. Do not
                    # leave rejected previews in persistent storage.
                    import_service._delete_preview(preview['id'])
                    raise ImportValidationError('；'.join(problems))
                result = import_service.confirm(preview['id'], preview['mapping'])
                rows = int(result.get('inserted_count') or 0) + int(result.get('updated_count') or 0)
                imported += rows
                print(f'Imported {filename}: {rows} rows, batch={result["id"]}')
            except Exception as error:
                failures.append(f'{filename}: {error}')
                print(f'FAILED {filename}: {error}', file=sys.stderr)

    if failures:
        print(f'Completed with {len(failures)} failure(s); imported rows: {imported}', file=sys.stderr)
        return 1
    print(f'Completed: {imported} rows imported through the canonical pipeline')
    return 0

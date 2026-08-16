"""Compatibility facade for historical file-import callers.

The old command-line and asynchronous upload entry points keep their response
shape, but all business data now goes through ImportService.
"""

import json
import os

from flask import has_app_context

from services.import_service import ImportValidationError, import_service


def import_file(filepath, *, source_type='auto', mapping_template=None):
    filename = os.path.basename(filepath)
    with open(filepath, 'rb') as handle:
        content = handle.read()

    def execute():
        selected_source = source_type
        if selected_source == 'auto':
            frame = import_service._read_workbook(content, filename)
            mapping = import_service._mapping(frame.columns)
            # Keep the historical entry point on the same source detector as
            # the HTTP/import-scan paths. The old filename heuristic could
            # misclassify channel/campaign/unit reports as product-day data
            # and only recognized DMP files whose filename contained "dmp".
            selected_source = import_service._detect_source_type(mapping)
        # Debugging aid intentionally kept silent in normal operation.
        preview = import_service.preview(filename, content, selected_source, mapping_template)
        if preview.get('required_unmapped'):
            raise ImportValidationError(
                '缺少必填字段映射: ' + ', '.join(preview['required_unmapped'])
            )
        if preview.get('invalid_rows') or preview.get('duplicate_keys'):
            raise ImportValidationError('导入预览质量校验未通过')
        return import_service.confirm(preview['id'], preview.get('mapping') or {})

    if has_app_context():
        return execute()
    from app import create_app
    app = create_app()
    with app.app_context():
        return execute()


def import_file_legacy_response(filepath, *, source_type='auto', mapping_template=None):
    result = import_file(filepath, source_type=source_type, mapping_template=mapping_template)
    quality = result.get('quality_summary') or {}
    if isinstance(quality, str):
        quality = json.loads(quality)
    return {
        'success': True,
        'total_rows': result.get('valid_rows') or result.get('total_rows') or quality.get('valid_rows', 0),
        'details': [{
            'sheet': filename if (filename := os.path.basename(filepath)) else 'import',
            'status': 'success',
            'rows': result.get('valid_rows') or quality.get('valid_rows', 0),
        }],
        'batch_id': result.get('id'),
        'source_type': result.get('source_type'),
        'source_filename': result.get('source_filename'),
        'quality_summary': quality,
    }

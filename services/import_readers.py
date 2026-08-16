"""Pure file readers for the canonical import engine."""

from services.import_service import ImportValidationError, import_service


class ImportReadError(ValueError):
    pass


def read_import_frame(content, filename):
    try:
        return import_service._read_workbook(content, filename)
    except ImportValidationError as error:
        raise ImportReadError(str(error)) from error

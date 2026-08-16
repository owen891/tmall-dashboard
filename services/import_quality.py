"""Pure quality validation facade."""

from services.import_service import import_service


def validate_frame(frame, mapping, spec, field_aliases=None, numeric_fields=None, percentage_fields=None):
    source_type = spec.name if hasattr(spec, 'name') else str(spec)
    return import_service._quality(frame, mapping, source_type)

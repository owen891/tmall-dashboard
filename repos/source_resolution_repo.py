"""Persistence adapter for source observations and field lineage."""

from services.source_resolution_service import (
    lineage_for_product_day,
    record_daily_observation,
)


class SourceResolutionRepo:
    """Keep source-governance SQL behind the repository boundary."""

    @staticmethod
    def record_daily_observation(
        connection,
        row,
        source_type,
        source_filename='',
        source_batch_id=None,
        source_system=None,
    ):
        return record_daily_observation(
            connection,
            row,
            source_type,
            source_filename=source_filename,
            source_batch_id=source_batch_id,
            source_system=source_system,
        )

    @staticmethod
    def lineage_for_product_day(connection, product_id, stat_date):
        return lineage_for_product_day(connection, product_id, stat_date)

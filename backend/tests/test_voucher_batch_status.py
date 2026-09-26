"""The status column must exist and default to None for legacy rows."""

from app.models.core import VoucherBatch


def test_voucher_batch_has_status_column():
    assert hasattr(VoucherBatch, "status")


def test_status_is_nullable_for_legacy_rows():
    # 21 batches predate this column in production; they must stay loadable.
    column = VoucherBatch.__table__.columns["status"]
    assert column.nullable is True

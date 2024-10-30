"""Test module for the `TransferResult` data model."""

from dcm_common.models.data_model import get_model_serialization_test

from dcm_transfer_module.models import TransferResult

test_transfer_result_json = get_model_serialization_test(
    TransferResult, (
        ((), {}),
        ((True,), {}),
    )
)

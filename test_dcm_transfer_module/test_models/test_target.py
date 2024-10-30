"""Test module for the `Target` data model."""

from pathlib import Path

from dcm_common.models.data_model import get_model_serialization_test

from dcm_transfer_module.models import Target


test_target_json = get_model_serialization_test(
    Target, (
        ((Path("."),), {}),
    )
)

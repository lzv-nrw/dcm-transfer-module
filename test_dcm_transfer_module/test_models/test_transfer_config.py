"""Test module for the `TransferConfig` data model."""

from pathlib import Path
from dcm_common.models.data_model import get_model_serialization_test

from dcm_transfer_module.models import Target, TransferConfig


test_transfer_config_json = get_model_serialization_test(
    TransferConfig, (
        ((Target(Path(".")),), {}),
    )
)

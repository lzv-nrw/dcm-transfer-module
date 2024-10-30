"""
TransferConfig data-model definition
"""

from dataclasses import dataclass

from dcm_common.models import DataModel

from dcm_transfer_module.models.target import Target


@dataclass
class TransferConfig(DataModel):
    """
    TransferConfig `DataModel`

    Keyword arguments:
    target -- `Target`-object pointing to SIP to be transferred
    """

    target: Target

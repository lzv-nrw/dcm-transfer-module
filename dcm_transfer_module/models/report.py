"""
Report data-model definition
"""

from dataclasses import dataclass, field

from dcm_common.orchestra import Report as BaseReport

from dcm_transfer_module.models.transfer_result import TransferResult


@dataclass
class Report(BaseReport):
    data: TransferResult = field(default_factory=TransferResult)

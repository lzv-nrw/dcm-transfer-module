"""
TransferResult data-model definition
"""

from typing import Optional
from dataclasses import dataclass

from dcm_common.models import DataModel


@dataclass
class TransferResult(DataModel):
    """
    TransferResult `DataModel`

    Keyword arguments:
    success -- overall success of the job
    """

    success: Optional[bool] = None

"""
Target data-model definition
"""

from dataclasses import dataclass
from pathlib import Path

from dcm_common.models import DataModel


@dataclass
class Target(DataModel):
    """
    Target `DataModel`

    Keyword arguments:
    path -- path to target directory/file relative to `FS_MOUNT_POINT`
    """

    path: Path

    @DataModel.serialization_handler("path")
    @classmethod
    def path_serialization(cls, value):
        """Performs `path`-serialization."""
        return str(value)

    @DataModel.deserialization_handler("path")
    @classmethod
    def path_deserialization(cls, value):
        """Performs `path`-deserialization."""
        return Path(value)

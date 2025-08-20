"""Input handlers for the 'DCM Transfer Module'-app."""

from pathlib import Path

from data_plumber_http import Property, Object, Url
from dcm_common.services import TargetPath, UUID

from dcm_transfer_module.models import Target, TransferConfig


def get_transfer_handler(cwd: Path):
    """
    Returns parameterized handler
    """
    return Object(
        properties={
            Property("transfer", required=True): Object(
                model=TransferConfig,
                properties={
                    Property("target", required=True): Object(
                        model=Target,
                        properties={
                            Property("path", required=True):
                                TargetPath(
                                    _relative_to=cwd, cwd=cwd, is_dir=True
                                )
                        },
                        accept_only=["path"]
                    ),
                },
                accept_only=[
                    "target",
                ]
            ),
            Property("token"): UUID(),
            Property("callbackUrl", name="callback_url"):
                Url(schemes=["http", "https"])
        },
        accept_only=["transfer", "token", "callbackUrl"]
    ).assemble()

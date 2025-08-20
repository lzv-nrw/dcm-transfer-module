"""
Test module for the `dcm_transfer_module/handlers.py`.
"""

import pytest
from data_plumber_http.settings import Responses

from dcm_transfer_module.models import TransferConfig
from dcm_transfer_module import handlers


@pytest.fixture(name="transfer_handler")
def _transfer_handler(fixtures):
    return handlers.get_transfer_handler(
        fixtures
    )


@pytest.mark.parametrize(
    ("json", "status"),
    (pytest_args := [
        (
            {"no-transfer": None},
            400
        ),
        (  # missing target
            {"transfer": {}},
            400
        ),
        (  # missing path
            {"transfer": {"target": {}}},
            400
        ),
        (
            {"transfer": {"target": {"path": "test_sip_"}}},
            404
        ),
        (
            {"transfer": {"target": {"path": "test_sip"}}},
            Responses.GOOD.status
        ),
        (
            {
                "transfer": {"target": {"path": "test_sip"}},
                "callbackUrl": None
            },
            422
        ),
        (
            {
                "transfer": {"target": {"path": "test_sip"}},
                "callbackUrl": "no.scheme/path"
            },
            422
        ),
        (
            {
                "transfer": {"target": {"path": "test_sip"}},
                "callbackUrl": "https://lzv.nrw/callback"
            },
            Responses.GOOD.status
        ),
        (
            {
                "transfer": {"target": {"path": "test_sip"}},
                "token": "https://lzv.nrw/callback"
            },
            422
        ),
        (
            {
                "transfer": {"target": {"path": "test_sip"}},
                "token": "non-uuid"
            },
            422
        ),
        (
            {
                "transfer": {"target": {"path": "test_sip"}},
                "token": "37ee72d6-80ab-4dcd-a68d-f8d32766c80d"
            },
            Responses.GOOD.status
        ),
    ]),
    ids=[f"stage {i+1}" for i in range(len(pytest_args))]
)
def test_transfer_handler(
    transfer_handler, json, status, fixtures
):
    "Test `validate_ip_handler`."

    output = transfer_handler.run(json=json)

    assert output.last_status == status
    if status != Responses.GOOD.status:
        print(output.last_message)
    else:
        assert isinstance(output.data.value["transfer"], TransferConfig)
        assert fixtures not in output.data.value["transfer"].target.path.parents

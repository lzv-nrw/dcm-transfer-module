"""
Test module for the package `dcm-transfer-module-sdk`.
"""

from time import sleep

import pytest
import dcm_transfer_module_sdk

from dcm_transfer_module import app_factory


@pytest.fixture(name="default_sdk", scope="module")
def _default_sdk():
    return dcm_transfer_module_sdk.DefaultApi(
        dcm_transfer_module_sdk.ApiClient(
            dcm_transfer_module_sdk.Configuration(host="http://localhost:8080")
        )
    )


@pytest.fixture(name="transfer_sdk", scope="module")
def _transfer_sdk():
    return dcm_transfer_module_sdk.TransferApi(
        dcm_transfer_module_sdk.ApiClient(
            dcm_transfer_module_sdk.Configuration(host="http://localhost:8080")
        )
    )


def test_default_ping(
    default_sdk: dcm_transfer_module_sdk.DefaultApi,
    testing_config,
    run_service,
):
    """Test default endpoint `/ping-GET`."""

    run_service(from_factory=lambda: app_factory(testing_config()), port=8080)

    response = default_sdk.ping()

    assert response == "pong"


def test_default_status(
    default_sdk: dcm_transfer_module_sdk.DefaultApi,
    testing_config,
    run_service,
):
    """Test default endpoint `/status-GET`."""

    run_service(from_factory=lambda: app_factory(testing_config()), port=8080)

    response = default_sdk.get_status()

    assert response.ready


def test_default_identify(
    default_sdk: dcm_transfer_module_sdk.DefaultApi,
    run_service,
    testing_config,
):
    """Test default endpoint `/identify-GET`."""

    run_service(from_factory=lambda: app_factory(testing_config()), port=8080)

    response = default_sdk.identify()

    assert response.to_dict() == testing_config().CONTAINER_SELF_DESCRIPTION


def test_transfer_report(
    transfer_sdk: dcm_transfer_module_sdk.TransferApi,
    run_service,
    testing_config,
    minimal_request_body,
):
    """Test endpoints `/transfer-POST` and `/report-GET`."""

    run_service(from_factory=lambda: app_factory(testing_config()), port=8080)

    submission = transfer_sdk.transfer(minimal_request_body)

    while True:
        try:
            report = transfer_sdk.get_report(token=submission.value)
            break
        except dcm_transfer_module_sdk.exceptions.ApiException as e:
            assert e.status == 503
            sleep(0.1)

    assert report.data.success
    assert (
        testing_config.REMOTE_DESTINATION
        / minimal_request_body["transfer"]["target"]["path"]
    ).is_dir()


def test_transfer_report_404(
    transfer_sdk: dcm_transfer_module_sdk.TransferApi,
    testing_config,
    run_service,
):
    """Test transfer endpoint `/report-GET` without previous submission."""

    run_service(from_factory=lambda: app_factory(testing_config()), port=8080)

    with pytest.raises(dcm_transfer_module_sdk.rest.ApiException) as exc_info:
        transfer_sdk.get_report(token="some-token")
    assert exc_info.value.status == 404

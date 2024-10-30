"""Test-module for transfer-endpoint."""

from uuid import uuid4
from time import sleep
from unittest.mock import patch
import pytest

from dcm_common import Logger, LoggingContext as Context
from dcm_common.util import get_output_path

from dcm_transfer_module import app_factory


@pytest.mark.parametrize(
    ("pkey", "pkey_alg", "valid"),
    [
        ("pkey", "rsa", True),
        ("pkey", None, False),
        (None, "rsa", False)
    ],
    ids=["ok", "missing-alg", "missing-key"]
)
def test_app_factory_ssh_fingerprint_config(
    pkey, pkey_alg, valid, testing_config
):
    """Test function `app_factory` with bad fingerprint config."""
    testing_config.SSH_HOST_PUBLIC_KEY = pkey
    testing_config.SSH_HOST_PUBLIC_KEY_ALGORITHM = pkey_alg
    if valid:
        app_factory(testing_config())
    else:
        with pytest.raises(RuntimeError):
            app_factory(testing_config())


def test_transfer_minimal(
    client, minimal_request_body, testing_config, wait_for_report
):
    """Test basic functionality of /transfer-POST endpoint."""
    assert not (
        testing_config().REMOTE_DESTINATION
        / minimal_request_body["transfer"]["target"]["path"]
    ).is_dir()

    # submit job
    response = client.post(
        "/transfer",
        json=minimal_request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 201
    assert response.mimetype == "application/json"
    token = response.json["value"]

    # wait until job is completed
    json = wait_for_report(client, token)

    assert (
        testing_config().REMOTE_DESTINATION
        / minimal_request_body["transfer"]["target"]["path"]
    ).is_dir()
    assert json["data"]["success"]


def test_transfer_minimal_remote(
    client_remote, minimal_request_body, wait_for_report,
    remote_storage
):
    """
    Test basic functionality of /transfer-POST endpoint using remote
    server.
    """
    # submit job
    response = client_remote.post(
        "/transfer",
        json=minimal_request_body
    )
    assert client_remote.put("/orchestration?until-idle", json={}).status_code == 200
    json = wait_for_report(client_remote, response.json["value"])

    assert (
        remote_storage / minimal_request_body["transfer"]["target"]["path"]
    ).is_dir()
    assert json["data"]["success"]


@pytest.mark.parametrize(
    "overwrite_existing",
    [True, False],
    ids=["overwrite", "abort"]
)
def test_transfer_dst_exists(
    overwrite_existing, testing_config, minimal_request_body, wait_for_report
):
    """
    Test /transfer-POST endpoint when output destination already exists.
    """

    # setup client with given settings
    class TestingConfig(testing_config):
        OVERWRITE_EXISTING = overwrite_existing
    client = app_factory(TestingConfig()).test_client()

    # Create output destination in target
    target_dst = (
        testing_config().REMOTE_DESTINATION /
        minimal_request_body["transfer"]["target"]["path"]
    )
    target_dst.mkdir(parents=True)
    assert not (target_dst / "payload.txt").is_file()

    # submit job
    response = client.post(
        "/transfer",
        json=minimal_request_body
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    # wait until job is completed
    json = wait_for_report(client, response.json["value"])

    assert json["data"]["success"] is overwrite_existing
    if overwrite_existing:
        assert (target_dst / "payload.txt").is_file()
        assert Context.WARNING.name in json["log"]
        assert any(
            f"Conflicting transfer destination '{target_dst}'" in msg["body"]
            for msg in json["log"][Context.WARNING.name]
        )
    else:
        assert not (target_dst / "payload.txt").is_file()
        assert Context.ERROR.name in json["log"]
        assert any(
            f"target destination '{target_dst}' already exists." in msg["body"]
            for msg in json["log"][Context.ERROR.name]
        )


def test_transfer_dst_exists_fail(
    testing_config, minimal_request_body, wait_for_report
):
    """
    Test /transfer-POST endpoint when output destination already exists
    but rm fails.
    """

    # setup client with given settings
    class TestingConfig(testing_config):
        OVERWRITE_EXISTING = True
    client = app_factory(TestingConfig()).test_client()

    # Create output destination in target
    target_dst = (
        testing_config().REMOTE_DESTINATION /
        minimal_request_body["transfer"]["target"]["path"]
    )
    target_dst.mkdir(parents=True)
    err_msg = "Bad event."
    with patch(
        "dcm_transfer_module.components.transfer.TransferManager.rm",
        return_value=(1, "", err_msg)
    ):
        # submit job
        response = client.post(
            "/transfer",
            json=minimal_request_body
        )
        assert client.put("/orchestration?until-idle", json={}).status_code == 200

        # wait until job is completed
        json = wait_for_report(client, response.json["value"])

    assert json["data"]["success"] is False
    assert Context.ERROR.name in json["log"]
    assert any(
        "Conflicting transfer destination" in msg["body"]
        for msg in json["log"][Context.ERROR.name]
    )
    assert any(
        err_msg in msg["body"]
        for msg in json["log"][Context.ERROR.name]
    )


@pytest.fixture(name="mock_transfer_return")
def _mock_transfer_return():
    def _(i):
        log = Logger(default_origin="Transfer Manager")
        log.log(
            Context.ERROR,
            body="some error, call no " + str(i)
        )
        return log
    return _


def test_transfer_retries(
    testing_config, minimal_request_body, wait_for_report,
    mock_transfer_return
):
    """Test /transfer-POST endpoint for repeated transfer attempts."""

    # setup client with given settings
    class TestingConfig(testing_config):
        # Set config parameters to reduce the execution time
        TRANSFER_RETRIES = 3
        TRANSFER_RETRY_INTERVAL = 0.1
    client = app_factory(TestingConfig()).test_client()

    with patch(
        "dcm_transfer_module.components.transfer.TransferManager.transfer",
        side_effect=[
            mock_transfer_return(i)
            for i in range(1 + TestingConfig.TRANSFER_RETRIES)
        ]
    ):

        # submit job
        response = client.post(
            "/transfer",
            json=minimal_request_body
        )
        assert client.put("/orchestration?until-idle", json={}).status_code == 200

        # wait until job is completed
        json = wait_for_report(client, response.json["value"])

    assert not (
        TestingConfig.REMOTE_DESTINATION
        / minimal_request_body["transfer"]["target"]["path"]
    ).is_dir()
    assert json["data"]["success"] is False
    # The number of error messages in log is
    # 1 (base call)
    # + TestingConfig.TRANSFER_RETRIES
    # + 1 (extra msg from view function after result evaluation)
    assert len(json["log"]["ERROR"]) == \
        1 + TestingConfig.TRANSFER_RETRIES + 1
    # The expected errors for all calls appear in log
    for i in range(1 + TestingConfig.TRANSFER_RETRIES):
        for e in (
            mock_transfer_return(i).json["ERROR"]
        ):
            assert any(
                e["body"] in msg["body"]
                for msg in json["log"]["ERROR"]
            )
    # The final error message appears in log
    assert json["log"]["ERROR"][-1]["body"] == "SIP transfer failed."


def test_transfer_progress(
    testing_config, file_storage, wait_for_report
):
    """Test /transfer-POST endpoint where progress is tracked."""

    # setup client with given settings
    class TestingConfig(testing_config):
        BW_LIMIT = 10
    client = app_factory(TestingConfig()).test_client()

    # generate test-data
    test_sip = get_output_path(file_storage)
    payload_file = str(uuid4()) + ".txt"
    # The file size has to be sufficiently large
    (test_sip / payload_file).write_bytes(b"payload"*10000)

    # submit job
    response = client.post(
        "/transfer",
        json={
            "transfer": {
                "target": {
                    "path": str(test_sip.relative_to(file_storage))
                }
            }
        }
    )
    assert client.put("/orchestration?until-idle", json={}).status_code == 200

    assert response.status_code == 201
    assert response.mimetype == "application/json"
    token = response.json["value"]

    # get report while job is in process, with progress > 0
    max_sleep = 250
    c_sleep = 0
    while c_sleep < max_sleep:
        sleep(0.1)
        response = client.get(
            f"/report?token={token}"
        )
        if response.json["progress"]["numeric"] > 0:
            break
        c_sleep = c_sleep + 1

    print("Current progress: ", response.json["progress"])
    assert response.json["progress"]["numeric"] < 100
    assert response.json["progress"]["status"] == "running"
    assert f"syncing files, {response.json['progress']['numeric']}" \
        in response.json["progress"]["verbose"]

    # wait until job is completed
    json = wait_for_report(client, token)
    assert json["progress"]["numeric"] == 100
    assert json["progress"]["status"] == "completed"
    assert json["data"]["success"] is True


def test_transfer_no_connection_remote(
    testing_config_remote, minimal_request_body, wait_for_report
):
    """
    Test error-behavior for failing connection to remote in
    /transfer-GET.
    """

    class TestingConfig(testing_config_remote):
        SSH_USERNAME = "foo2"
    client_remote = app_factory(TestingConfig()).test_client()

    # submit job
    response = client_remote.post(
        "/transfer",
        json=minimal_request_body
    )
    assert client_remote.put("/orchestration?until-idle", json={}).status_code == 200
    json = wait_for_report(client_remote, response.json["value"])

    assert not json["data"]["success"]
    assert Context.ERROR.name in json["log"]
    assert any(
        "Unable to establish connection" in msg["body"]
        for msg in json["log"]["ERROR"]
    )

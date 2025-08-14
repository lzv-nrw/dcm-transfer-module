from pathlib import Path
from shutil import rmtree

import pytest
from dcm_common.services.tests import (
    fs_setup, fs_cleanup, wait_for_report, external_service, run_service
)
from dcm_common.util import get_output_path

from dcm_transfer_module import app_factory
from dcm_transfer_module.config import AppConfig


@pytest.fixture(scope="session", name="remote_storage")
def _remote_storage():
    return Path("test_dcm_transfer_module/remote_storage/")


@pytest.fixture(scope="session", name="remote_storage_server")
def _remote_storage_server():
    return Path("/remote_storage")


@pytest.fixture(scope="session", autouse=True)
def remote_setup(
    request, remote_storage
):
    """
    Set up and clean up remote_storage
    """

    def clean():
        if remote_storage.is_dir():
            for x in remote_storage.glob("*"):
                if x.is_dir():
                    rmtree(x)
                else:
                    x.unlink()
    clean()
    request.addfinalizer(clean)


@pytest.fixture(scope="session", name="file_storage")
def _file_storage():
    return Path("test_dcm_transfer_module/file_storage/")


@pytest.fixture(scope="session", name="fixtures")
def _fixtures():
    return Path("test_dcm_transfer_module/fixtures/")


@pytest.fixture(scope="session", autouse=True)
def prepare_key_fixtures(fixtures):
    """Sets correct file access permissions for ssh-key fixtures."""
    (fixtures / ".ssh" / "id_rsa").chmod(0o600)
    (fixtures / ".ssh" / "id_rsa_bad").chmod(0o600)


@pytest.fixture(scope="session", autouse=True)
def disable_extension_logging():
    """
    Disables the stderr-logging via the helper method `print_status`
    of the `dcm_common.services.extensions`-subpackage.
    """
    # pylint: disable=import-outside-toplevel
    from dcm_common.services.extensions.common import PrintStatusSettings

    PrintStatusSettings.silent = True


@pytest.fixture(name="testing_config")
def _testing_config(file_storage):
    """Returns test-config"""
    # setup config-class
    class TestingConfig(AppConfig):
        ORCHESTRATION_AT_STARTUP = False
        ORCHESTRATION_DAEMON_INTERVAL = 0.001
        ORCHESTRATION_ORCHESTRATOR_INTERVAL = 0.001
        ORCHESTRATION_ABORT_NOTIFICATIONS_STARTUP_INTERVAL = 0.01

        TESTING = True
        FS_MOUNT_POINT = file_storage
        LOCAL_TRANSFER = True
        REMOTE_DESTINATION = file_storage.resolve() / "remote"

    return TestingConfig


@pytest.fixture(name="testing_config_remote")
def _testing_config_remote(testing_config, remote_storage_server):
    """Returns test-config for transfer to remote server"""
    # config for remote server
    class TestingConfig(testing_config):
        ORCHESTRATION_AT_STARTUP = False
        ORCHESTRATION_DAEMON_INTERVAL = 0.001
        ORCHESTRATION_ORCHESTRATOR_INTERVAL = 0.001

        LOCAL_TRANSFER = False
        SSH_USERNAME = "foo"
        SSH_PORT = 2222
        SSH_IDENTITY_FILE = Path(
            "test_dcm_transfer_module/fixtures/.ssh/id_rsa"
        )
        REMOTE_DESTINATION = remote_storage_server
        SSH_CLIENT_OPTIONS = [
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
        ]
        TRANSFER_OPTIONS = ["--chmod=a+rw"]

    return TestingConfig


@pytest.fixture(name="client")
def _client(testing_config):
    """
    Returns test_client.
    """
    return app_factory(testing_config(), block=True).test_client()


@pytest.fixture(name="client_remote")
def _client_remote(testing_config_remote):
    """
    Returns test_client for testing_config_remote.
    """
    return app_factory(testing_config_remote(), block=True).test_client()


@pytest.fixture(name="test_sip")
def _test_sip(file_storage):
    """Create a test-SIP and returns path relative to `file_storage`."""
    test_sip = get_output_path(file_storage)
    (test_sip / "payload.txt").touch()
    return test_sip.relative_to(file_storage)


@pytest.fixture(name="minimal_request_body")
def _minimal_request_body(test_sip):
    """Returns minimal request body filled with test-SIP path."""
    return {
        "transfer": {
            "target": {
                "path": str(test_sip)
            },
        },
    }

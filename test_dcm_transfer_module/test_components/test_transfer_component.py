"""TransferManager-component test-module."""

from pathlib import Path
from uuid import uuid4
import re
import subprocess
import os

import pytest
from dcm_common import LoggingContext as Context

from dcm_transfer_module.components import SSHClient, TransferManager


def get_data_sent(f) -> int:
    """Helper for parsing rsync output."""
    return int(re.findall(
        r".*sent (\d*).*",
        f.read_text(encoding="utf8")
    )[0])


@pytest.fixture(name="ssh_client")
def _ssh_client():
    return SSHClient(
        host=os.environ.get("SSH_HOSTNAME") or "localhost",
        user="foo",
        port=2222,
        identity_file=Path("test_dcm_transfer_module/fixtures/.ssh/id_rsa"),
        batch_mode=True,
        default_options=[
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR",
        ]
    )


@pytest.fixture(name="get_ssh_client_with_fingerprint")
def _get_ssh_client_with_fingerprint():
    def _(use_fingerprint: bool) -> SSHClient:
        """
        Returns `SSHClient` with the test-server's fingerprint registered.
        """
        keyscan = subprocess.run(
            [
                "ssh-keyscan", "-p", "2222", "-t", "ed25519",
                os.environ.get("SSH_HOSTNAME") or "localhost"
            ], capture_output=True, check=False, text=True
        )
        return SSHClient(
            host=os.environ.get("SSH_HOSTNAME") or "localhost",
            user="foo",
            port=2222,
            identity_file=Path("test_dcm_transfer_module/fixtures/.ssh/id_rsa"),
            batch_mode=True,
            fingerprint=(
                keyscan.stdout.split("\n")[0].split()[1],
                keyscan.stdout.split("\n")[0].split()[2]
            ) if use_fingerprint else None
        )
    return _


@pytest.fixture(name="ssh_tm")
def _ssh_tm(ssh_client):
    return TransferManager(
        ssh_client,
        default_options=[
            "-a", "--info=progress2",
            "--chmod=a+rw",
        ]
    )


def test_query_remote_minimal(ssh_client: SSHClient):
    """
    Test method `query_remote` of `SSHClient` with minimal command.
    """

    query = ssh_client.query_remote("echo 'Hello World!'")
    assert query.stdout == "Hello World!\n"
    assert query.returncode == 0


def test_query_remote(ssh_client: SSHClient):
    """
    Test method `query_remote` of `SSHClient`.
    """
    cmd = "hostname"
    assert ssh_client.query_remote(cmd) != subprocess.check_output(cmd)


@pytest.mark.parametrize(
    "use_fingerprint",
    [True, False],
    ids=["with-fingerprint", "without-fingerprint"]
)
def test_query_remote_fingerprint(
    use_fingerprint, get_ssh_client_with_fingerprint
):
    """
    Test method `query_remote` of `SSHClient` with and without
    fingerprint of remote.
    """
    client = get_ssh_client_with_fingerprint(use_fingerprint)
    query = client.query_remote("hostname")
    if use_fingerprint:
        assert query.returncode == 0
    else:
        assert query.returncode == 255
        assert query.stderr != ""


def test_query_remote_fs(
    ssh_client: SSHClient, remote_storage: Path, remote_storage_server: Path
):
    """Test method `query_remote` of `SSHClient`."""

    file = str(uuid4())
    ssh_client.query_remote(f"touch {remote_storage_server / file}")
    assert (remote_storage / file).exists()
    ssh_client.query_remote(f"rm {remote_storage_server / file}")
    assert not (remote_storage / file).exists()


def test_query_remote_failed_auth():
    """Test ssh-connection with bad key."""
    tm = SSHClient(
        host=os.environ.get("SSH_HOSTNAME") or "localhost",
        user="foo2",
        port=2222,
        identity_file=Path("test_dcm_transfer_module/fixtures/.ssh/id_rsa_bad"),
        batch_mode=True,
        default_options=[
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "PasswordAuthentication=no",
        ]
    )
    query = tm.query_remote("echo 'Hello World!'")
    assert query.returncode != 0


def test_dir_exists_local(file_storage: Path):
    """Test method `dir_exists` of `TransferManager` in local mode."""

    dir_ = str(uuid4())
    (file_storage / dir_).mkdir(parents=True, exist_ok=True)
    assert TransferManager().dir_exists(file_storage / dir_)


def test_file_exists_local(file_storage: Path):
    """Test method `file_exists` of `TransferManager` in local mode."""

    file = str(uuid4())
    (file_storage / file).touch(exist_ok=True)
    assert TransferManager().file_exists(file_storage / file)


def test_dir_exists_true(
    ssh_tm: TransferManager, remote_storage: Path, remote_storage_server: Path
):
    """Test method `dir_exists` of `TransferManager`."""

    dir_ = str(uuid4())
    (remote_storage / dir_).mkdir(parents=True, exist_ok=True)
    assert ssh_tm.dir_exists(remote_storage_server / dir_)


def test_dir_exists_false(
    ssh_tm: TransferManager, remote_storage: Path, remote_storage_server: Path
):
    """Test method `dir_exists` of `TransferManager`."""

    file = str(uuid4())
    assert not ssh_tm.dir_exists(remote_storage_server / file)
    (remote_storage / file).touch(exist_ok=True)
    assert not ssh_tm.dir_exists(remote_storage_server / file)


def test_file_exists_true(
    ssh_tm: TransferManager, remote_storage: Path, remote_storage_server: Path
):
    """Test method `file_exists` of `TransferManager`."""

    file = str(uuid4())
    (remote_storage / file).touch(exist_ok=True)
    assert ssh_tm.file_exists(remote_storage_server / file)


def test_file_exists_false(
    ssh_tm: TransferManager, remote_storage: Path
):
    """Test method `file_exists` of `TransferManager`."""

    assert not ssh_tm.file_exists(Path(str(uuid4())))
    dir_ = str(uuid4())
    (remote_storage / dir_).mkdir(parents=True, exist_ok=True)
    assert not ssh_tm.file_exists(Path(dir_))


def test_rm_not_exists_local(file_storage: Path):
    """
    Test method `rm` of `TransferManager` in local mode for non-existing
    target.
    """

    file = str(uuid4())
    assert not (file_storage / file).exists()
    TransferManager().rm(file_storage / file)


def test_rm_exists_file_local(file_storage: Path):
    """
    Test method `rm` of `TransferManager` in local mode for existing
    file.
    """

    file = str(uuid4())
    (file_storage / file).touch()
    TransferManager().rm(file_storage / file)
    assert not (file_storage / file).exists()


def test_rm_exists_dir_local(file_storage: Path):
    """
    Test method `rm` of `TransferManager` in local mode for existing
    directory.
    """

    dir_ = str(uuid4())
    (file_storage / dir_).mkdir(parents=True)
    TransferManager().rm(file_storage / dir_)
    assert not (file_storage / dir_).exists()


def test_rm_not_exists(
    ssh_tm: TransferManager,
    remote_storage: Path, remote_storage_server: Path
):
    """
    Test method `rm` of `TransferManager` for non-existing target.
    """

    file = str(uuid4())
    assert not (remote_storage / file).exists()
    query = ssh_tm.rm(remote_storage_server / file)
    assert query[0] == 0  # rm is being run with -f


def test_rm_exists_file(
    ssh_tm: TransferManager,
    remote_storage: Path, remote_storage_server: Path
):
    """Test method `rm` of `TransferManager` for existing file."""

    file = str(uuid4())
    (remote_storage / file).touch()
    query = ssh_tm.rm(remote_storage_server / file)
    assert query[0] == 0
    assert not (remote_storage / file).exists()


def test_rm_exists_dir(
    ssh_tm: TransferManager,
    remote_storage: Path, remote_storage_server: Path
):
    """Test method `rm` of `TransferManager` for existing directory."""

    dir_ = str(uuid4())
    (remote_storage / dir_).mkdir(parents=True)
    query = ssh_tm.rm(remote_storage_server / dir_)
    assert query[0] == 0
    assert not (remote_storage / dir_).exists()


def test_transfer_local(file_storage: Path, remote_storage: Path):
    """
    Test method `transfer` of `TransferManager` for local configuration.
    """

    file = str(uuid4())
    (file_storage / file).write_bytes(b"test-local")
    TransferManager().transfer(file_storage / file, remote_storage / file)
    assert (remote_storage / file).read_bytes() == b"test-local"


def test_transfer_ssh(
    ssh_tm: TransferManager,
    file_storage: Path, remote_storage: Path, remote_storage_server: Path
):
    """
    Test method `transfer` of `TransferManager` for ssh configuration.
    """

    file = str(uuid4())
    (file_storage / file).write_bytes(b"test-ssh")
    ssh_tm.transfer(file_storage / file, remote_storage_server / file)
    assert (remote_storage / file).read_bytes() == b"test-ssh"


@pytest.mark.parametrize(
    "use_fingerprint",
    [True, False],
    ids=["with-fingerprint", "without-fingerprint"],
)
def test_transfer_ssh_fingerprint(
    use_fingerprint, get_ssh_client_with_fingerprint,
    file_storage: Path, remote_storage: Path, remote_storage_server: Path
):
    """
    Test method `transfer` of `TransferManager` for ssh configuration
    with fingerprint.
    """

    # setup transfer manager
    ssh_tm = TransferManager(
        get_ssh_client_with_fingerprint(use_fingerprint),
        default_options=[
            "-a", "--info=progress2",
            "--chmod=a+rw",
        ]
    )

    file = str(uuid4())
    (file_storage / file).write_bytes(b"test-ssh")
    log = ssh_tm.transfer(file_storage / file, remote_storage_server / file)
    if use_fingerprint:
        assert Context.ERROR not in log
        assert (remote_storage / file).read_bytes() == b"test-ssh"
    else:
        assert Context.ERROR in log
        assert not (remote_storage / file).exists()


def test_transfer_directory(file_storage: Path, remote_storage: Path):
    """
    Test method `transfer` of `TransferManager` for transferring
    directory.
    """

    dir_ = str(uuid4())
    file = str(uuid4())
    (file_storage / dir_).mkdir(parents=True, exist_ok=False)
    (file_storage / dir_ / file).touch()
    TransferManager().transfer(file_storage / dir_, remote_storage / dir_)
    assert (remote_storage / dir_ / file).exists()


def test_transfer_directory_ssh(
    ssh_tm: TransferManager,
    file_storage: Path, remote_storage: Path, remote_storage_server: Path
):
    """
    Test method `transfer` of `TransferManager` for ssh configuration.
    """

    dir_ = str(uuid4())
    file = str(uuid4())
    (file_storage / dir_).mkdir(parents=True, exist_ok=False)
    (file_storage / dir_ / file).touch()
    ssh_tm.transfer(file_storage / dir_, remote_storage_server / dir_)
    assert (remote_storage / dir_ / file).exists()


@pytest.mark.parametrize(
    "make_progress_file",
    [
        lambda file_storage, progress_file: file_storage / progress_file,
        lambda file_storage, progress_file:
            open(str(file_storage / progress_file), "w", encoding="utf-8"),
    ],
    ids=["path", "file"]
)
def test_transfer_progress_file(
    make_progress_file, file_storage: Path, remote_storage: Path
):
    """
    Test method `transfer` of `TransferManager` with `progress_file`.
    """

    payload_file = str(uuid4())
    progress_file = str(uuid4())
    (file_storage / payload_file).touch()
    TransferManager().transfer(
        file_storage / payload_file,
        remote_storage / payload_file,
        progress_file=make_progress_file(file_storage, progress_file)
    )
    assert (remote_storage / payload_file).exists()
    assert (file_storage / progress_file).exists()
    assert b"100%" in (file_storage / progress_file).read_bytes()


@pytest.mark.parametrize(
    "mirror",
    [
        True, False
    ],
    ids=["mirror", "no-mirror"]
)
def test_transfer_mirror(
    mirror, file_storage: Path, remote_storage: Path
):
    """
    Test method `transfer` of `TransferManager` with `mirror`.

    Create directory on both local and remote storage. Initially both
    contain different files. If `mirror` is set, after transferring the
    directory, both should be identical.
    """

    payload_dir = str(uuid4())
    payload_file1 = str(uuid4())
    payload_file2 = str(uuid4())

    (file_storage / payload_dir).mkdir(exist_ok=False)
    (remote_storage / payload_dir).mkdir(exist_ok=False)
    (file_storage / payload_dir / payload_file1).touch()
    (remote_storage / payload_dir / payload_file2).touch()

    TransferManager().transfer(
        file_storage / payload_dir,
        remote_storage / payload_dir,
        mirror=mirror
    )
    assert (remote_storage / payload_dir / payload_file1).exists()
    assert (remote_storage / payload_dir / payload_file2).exists() != mirror


def test_transfer_compress(file_storage: Path, remote_storage: Path):
    """
    Test method `transfer` of `TransferManager` with `compress`.
    """

    # generate test-data that is well-compressible
    payload_file = str(uuid4())
    (file_storage / payload_file).write_bytes(b"payload"*100)

    # send without compression
    progress_file = str(uuid4())
    TransferManager(default_options=["-v"]).transfer(
        file_storage / payload_file,
        remote_storage / str(uuid4()),
        progress_file=file_storage / progress_file,
        use_compression=False
    )
    uncompressed = get_data_sent(file_storage / progress_file)

    # send with compression
    TransferManager(default_options=["-v"]).transfer(
        file_storage / payload_file,
        remote_storage / str(uuid4()),
        progress_file=file_storage / progress_file,
        use_compression=True
    )
    compressed = get_data_sent(file_storage / progress_file)

    # check results
    print(f"compression ratio: {compressed/uncompressed}")
    assert uncompressed > compressed


def test_transfer_compression_level(file_storage: Path, remote_storage: Path):
    """
    Test method `transfer` of `TransferManager` with `compression_level`.
    """

    # generate test-data that is well-compressible
    payload_file = str(uuid4())
    # The file size has to be sufficiently large in order to get a noticeable
    # difference between the compression levels
    (file_storage / payload_file).write_bytes(b"payload"*200000)

    # send with compression level 1 (fastest)
    progress_file = str(uuid4())
    TransferManager(default_options=["-v"]).transfer(
        file_storage / payload_file,
        remote_storage / str(uuid4()),
        progress_file=file_storage / progress_file,
        use_compression=True,
        compression_level=1
    )
    compressed_level_1 = get_data_sent(file_storage / progress_file)

    # send with compression level 9 (most compressed)
    TransferManager(default_options=["-v"]).transfer(
        file_storage / payload_file,
        remote_storage / str(uuid4()),
        progress_file=file_storage / progress_file,
        use_compression=True,
        compression_level=9
    )
    compressed_level_9 = get_data_sent(file_storage / progress_file)

    # check results
    print(
        f"ratio of compression levels: {compressed_level_9/compressed_level_1}"
    )
    assert compressed_level_1 > compressed_level_9


def test_transfer_stderr(file_storage: Path, remote_storage: Path):
    """
    Test method `transfer` of `TransferManager` with an error,
    when the source file does not exist.
    """

    # Create src filename but do not generate file
    file = str(uuid4())
    # Attempt to transfer the file
    log = TransferManager().transfer(
        file_storage / file,
        remote_storage / file,
    )
    assert any(
        file + '" failed: No such file or directory' in msg["body"]
        for msg in log.json["ERROR"]
    )

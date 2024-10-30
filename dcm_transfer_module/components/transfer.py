"""
This module defines the `TransferManager` component of the Transfer
Module-app.

Its implementation is based on the `SSHClient` class, which provides a
simple interface for command execution on a remote system via SSH.
"""

from typing import Optional, TextIO
import os
from pathlib import Path
import subprocess
import io
from shutil import rmtree

from dcm_common import Logger, LoggingContext as Context


class SSHClient:
    """
    This class implements a minimal ssh-interface for a remote server.

    Keyword arguments:
    host -- remote server's hostname
    user -- username
            (default None)
    port -- remote server's port
            (default None)
    identity_file -- path to ssh-private key file
                     (default None)
    fingerprint -- tuple containing acceptable remote fingerprint
                   information; format: (algorithm, public-key)
                   view possible algorithms with `ssh -Q key` and the
                   remote's fingerprint with `ssh-keyscan`
                   (default None)
    batch_mode -- whether to use batch mode
                  (default False)
    default_options -- default options used in a transfer-call
                       (default None; corresponds to [])
    """
    def __init__(
        self,
        host: str,
        user: Optional[str] = None,
        port: Optional[int | str] = None,
        identity_file: Optional[Path] = None,
        fingerprint: Optional[tuple[str, str]] = None,
        batch_mode: Optional[bool] = False,
        default_options: Optional[list[str]] = None,
    ) -> None:
        self._host = host
        self._user = user
        self._port = port if port is None else str(port)
        self._identity_file = identity_file
        self._fingerprint = fingerprint
        self._batch_mode = batch_mode
        self.default_options = (
            default_options
            if default_options is not None else []
        )

    @property
    def command(self):
        """Returns a string with the ssh client command."""
        return "ssh"

    @property
    def identity(self) -> list[str]:
        """
        Returns a list of arguments ["-i", "..."] specifying the
        identity file for an ssh client. The list remains empty, if no
        identity file is specified.
        """
        return (
            ["-i", str(self._identity_file.resolve())]
            if self._identity_file else []
        )

    @property
    def port(self) -> list[str]:
        """
        Returns a list of arguments ["-p", "..."] specifying the port
        for an ssh client. The list remains empty, if no port is
        specified.
        """
        return (
            ["-p", str(self._port)]
            if self._port else []
        )

    def fingerprint(self, quote_command: bool = False) -> list[str]:
        """
        Returns a list of arguments ["-o", "KnownHostsCommand=..."]
        specifying the remote's fingerprint for an ssh connection. The
        list is empty if no fingerprint was specified during
        instantiation.

        This implementation uses the `KnownHostsCommand`-option.

        Keyword arguments:
        quote_command -- if `True`, the KnownHostCommand will be quoted
                         (can be used to construct a literal
                         ssh-command)
                         (default False)
        """
        if self._fingerprint is None:
            return []
        if quote_command:
            quote = "'"
        else:
            quote = ""
        return [
            "-o",
            f"KnownHostsCommand={quote}/usr/bin/env printf "
            f'"%H {self._fingerprint[0]} {self._fingerprint[1]}"{quote}'
        ]

    @property
    def batch_mode(self) -> list[str]:
        if not self._batch_mode:
            return []
        return ["-o", "BatchMode=yes"]

    @property
    def destination(self) -> str:
        """
        Returns a string with the ssh destination according to user and
        host details.
        """
        if not self._host:
            return ""
        return str(self._user or "") + ("@" if self._user else "") + self._host

    def query_remote(self, cmd: str) -> subprocess.CompletedProcess:
        """
        Run a command on the remote host and return the process's
        `subprocess.CompletedProcess`-instance.

        Keyword arguments:
        cmd -- the command to run on the remote host
        """
        if not self._host:
            raise RuntimeError("This action requires a host.")
        _cmd = (
            [self.command]
            + self.default_options
            + self.fingerprint()
            + self.batch_mode
            + self.identity
            + self.port
            + [self.destination]
            + [cmd]
        )
        return subprocess.run(
            _cmd, capture_output=True, check=False, text=True
        )


class TransferManager:
    """
    In particular, a synchronous data transfer using rsync is
    implemented. Data transfer to a remote destination requires an
    `SSHClient`.

    Keyword arguments:
    ssh_client -- `SSHClient` for remote session; `TransferManager`
                  works locally if omitted
                  (default None)
    default_options -- default options used in a transfer-call
                       (default None; corresponds to
                       ["-a", "--info=progress2"])
    """

    def __init__(
        self,
        ssh_client: Optional[SSHClient] = None,
        default_options: Optional[list[str]] = None,
    ):
        self._ssh_client = ssh_client
        self.default_options = (
            default_options
            if default_options is not None
            else ["-a", "--info=progress2"]
        )

    @property
    def command(self):
        """Returns a string with the rsync client command."""
        return "rsync"

    def destination(self, dst: Path) -> str:
        """
        Returns a string with the rsync destination according to user and
        host details.
        """
        if self._ssh_client:
            return f"{self._ssh_client.destination}:{dst}"
        return str(dst)

    @property
    def shell(self) -> list[str]:
        """
        Returns a list of arguments ["-e", "ssh ..."] specifying the
        details for a remote shell. The list remains empty, if no host
        is specified (expected for local execution).
        """
        return (
            ["-e", f"""{self._ssh_client.command} {
                ' '.join(
                    self._ssh_client.default_options
                    + self._ssh_client.fingerprint(quote_command=True)
                    + self._ssh_client.batch_mode
                    + self._ssh_client.identity
                    + self._ssh_client.port
                )
            }"""]
            if self._ssh_client else []
        )

    def compression(
        self,
        use_compression: bool = False,
        compression_level: Optional[int] = None
    ) -> list[str]:
        """
        Returns a list of arguments ["-z", "..."] specifying the
        compression-settings for an rsync call. The list remains empty,
        if `use_compression` is false.

        Keyword arguments:
        use_compression -- whether to use compression for transfer
                           (default False)
        compression_level -- compression level for transfer
                             (default None - this means 6 in rsync context)
        """
        if not use_compression:
            return []
        return (
            ["-z"]
            + (
                ["--compress-level", str(compression_level)]
                if compression_level is not None else []
            )
        )

    def file_exists(self, dst: Path) -> bool:
        """
        Returns `True` if file `dst` exists in remote.

        If an SSHClient is set, the file existence check is performed
        on the remote host. Otherwise, the file existence check is
        performed locally.
        """
        if not self._ssh_client:
            return dst.is_file()
        return self._ssh_client.query_remote(
            f"[ -f '{dst}' ]"
        ).returncode == 0

    def dir_exists(self, dst: Path) -> bool:
        """
        Returns `True` if directory `dst` exists in remote.

        If an SSHClient is set, the file existence check is performed
        on the remote host. Otherwise, the file existence check is
        performed locally.
        """
        if not self._ssh_client:
            return dst.is_dir()
        return self._ssh_client.query_remote(
            f"[ -d '{dst}' ]"
        ).returncode == 0

    def rm(self, target: Path) -> tuple[int, str, str]:
        """
        Attempts to force delete `target` in remote.

        Returns a tuple of resulting exit code, stdout, and stderr.

        If an SSHClient is set, the deletion is performed on the remote
        host. Otherwise, the deletion is performed locally.

        Keyword arguments:
        target -- path to target dir or file
        """
        if not self._ssh_client:
            if target.is_dir():
                rmtree(target)
            elif target.is_file() or target.is_fifo():
                target.unlink()
            return 0, "", ""
        query = self._ssh_client.query_remote(
            f"rm -rf '{target}'"
        )
        return query.returncode, query.stdout, query.stderr

    def transfer(
        self,
        src: Path,
        dst: Path,
        transfer_timeout: Optional[int] = None,
        progress_file: Optional[TextIO | Path] = None,
        use_compression: bool = False,
        compression_level: Optional[int] = None,
        validate_checksums: bool = False,
        mirror: bool = False,
        partial: bool = False,
        resume: bool = False,
        bwlimit: int = 0
    ) -> Logger:
        """
        Performs a synchronous file transfer from `src` to `dst`.

        Keyword arguments:
        src -- source file/directory for transfer
        dst -- target file/directory for transfer
        transfer_timeout -- connection timeout in seconds
        progress_file -- output target to write progress information to;
                         if omitted, no stdout is written
                         (default None)
        use_compression -- whether to use compression for transfer
                           (default False)
        compression_level -- compression level for transfer
                             (default None)
        validate_checksums -- whether to validate results with checksums
                              (default False)
        mirror -- whether to delete files in remote that do not exist in
                  source
                  (default False)
        partial -- whether to support resuming after being interrupted
                   (default False)
        resume -- whether to resume interrupted transfers
                  (default False)
        bwlimit -- maximum transfer rate in units of 1024 bytes
                   (default 0 specifies no limit)
        """
        _cmd = (
            [self.command]
            + self.shell
            + self.compression(
                use_compression, compression_level
            )
            + (["--timeout=" + str(transfer_timeout)]
               if transfer_timeout else [])
            + (["-c"] if validate_checksums else [])
            + (["--delete"] if mirror else [])
            + (["--partial"] if partial else [])
            + (["--append"] if resume else [])
            + ["--bwlimit=" + str(bwlimit)]
            + self.default_options
            # os.sep to ensure trailing slash for directories
            # if omitted and destination dir already exists, rsync
            # will place directory src inside of dst instead of
            # working on contents of dst
            + [f"{src.resolve()}{os.sep if src.is_dir() else ''}"]
            + [self.destination(dst)]
        )

        # Initialize log
        log = Logger(default_origin="Transfer Manager")

        if progress_file is None:
            _stdout = subprocess.DEVNULL
        elif isinstance(progress_file, Path):
            _stdout = io.open(  # pylint: disable=consider-using-with
                progress_file, "w", encoding="utf-8"
            )
        else:
            _stdout = progress_file

        log.log(
            Context.EVENT,
            body=f"Starting transfer of '{src}'."
        )

        # Run command
        result = subprocess.run(
            _cmd,
            check=False,
            stdout=_stdout,
            stderr=subprocess.PIPE,
            text=True
        )

        # Write the stderr in the log
        if result.stderr != "":
            for line in result.stderr.strip().split("\n"):
                log.log(
                    (Context.WARNING if result.returncode == 0
                        else Context.ERROR),
                    body=line
                )

        if result.returncode == 0:
            log.log(
                Context.EVENT,
                body="Transfer complete."
            )
        else:
            log.log(
                Context.EVENT,
                body="Error encountered during transfer."
            )

        return log

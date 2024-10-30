"""Configuration module for the 'Transfer Module'-app."""

import os
from pathlib import Path
from importlib.metadata import version
import subprocess
import json

import yaml
from dcm_common.services import FSConfig, OrchestratedAppConfig
import dcm_transfer_module_api


class AppConfig(FSConfig, OrchestratedAppConfig):
    """
    Configuration for the 'Transfer Module'-app.
    """

    # ------ TRANSFER ------
    LOCAL_TRANSFER = (int(os.environ.get("LOCAL_TRANSFER") or 0)) == 1
    SSH_HOSTNAME = os.environ.get("SSH_HOSTNAME") or "localhost"
    SSH_PORT = int(os.environ.get("SSH_PORT") or 22)
    SSH_HOST_PUBLIC_KEY = os.environ.get("SSH_HOST_PUBLIC_KEY")
    SSH_HOST_PUBLIC_KEY_ALGORITHM = \
        os.environ.get("SSH_HOST_PUBLIC_KEY_ALGORITHM")
    SSH_BATCH_MODE = (int(os.environ.get("SSH_BATCH_MODE") or 1)) == 1
    SSH_USERNAME = os.environ.get("SSH_USERNAME") or "dcm"
    SSH_IDENTITY_FILE = Path(
        os.environ.get("SSH_IDENTITY_FILE") or "~/.ssh/id_rsa"
    )
    REMOTE_DESTINATION = Path(
        os.environ.get("REMOTE_DESTINATION") or "/remote_storage"
    )
    OVERWRITE_EXISTING = (int(os.environ.get("OVERWRITE_EXISTING") or 0)) == 1
    TRANSFER_TIMEOUT = int(os.environ.get("TRANSFER_TIMEOUT") or 3)
    USE_COMPRESSION = (int(os.environ.get("USE_COMPRESSION") or 0)) == 1
    COMPRESSION_LEVEL = int(
        os.environ.get("COMPRESSION_LEVEL") or 6
    )
    VALIDATE_CHECKSUMS = (int(os.environ.get("VALIDATE_CHECKSUMS") or 0)) == 1
    TRANSFER_RETRIES = int(os.environ.get("TRANSFER_RETRIES") or 3)
    TRANSFER_RETRY_INTERVAL = int(
        os.environ.get("TRANSFER_RETRY_INTERVAL") or 360
    )
    SSH_CLIENT_DEFAULT_OPTIONS = []
    SSH_CLIENT_OPTIONS = (
        json.loads(os.environ["SSH_CLIENT_OPTIONS"])
        if "SSH_CLIENT_OPTIONS" in os.environ else []
    )
    TRANSFER_DEFAULT_OPTIONS = ["-a", "--info=progress2"]
    TRANSFER_OPTIONS = (
        json.loads(os.environ["TRANSFER_OPTIONS"])
        if "TRANSFER_OPTIONS" in os.environ else []
    )
    BW_LIMIT = 0

    # ------ IDENTIFY ------
    # generate self-description
    API_DOCUMENT = \
        Path(dcm_transfer_module_api.__file__).parent / "openapi.yaml"
    API = yaml.load(
        API_DOCUMENT.read_text(encoding="utf-8"),
        Loader=yaml.SafeLoader
    )

    def set_identity(self) -> None:
        super().set_identity()
        self.CONTAINER_SELF_DESCRIPTION["description"] = (
            "This API provides SIP transfer-functionalities."
        )

        # version
        self.CONTAINER_SELF_DESCRIPTION["version"]["api"] = (
            self.API["info"]["version"]
        )
        self.CONTAINER_SELF_DESCRIPTION["version"]["app"] = version(
            "dcm-transfer-module"
        )
        try:
            self.CONTAINER_SELF_DESCRIPTION["version"]["software"]["ssh"] = (
                subprocess.run(
                    ["ssh", "-V"], capture_output=True, text=True, check=True
                ).stderr.strip()
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            self.CONTAINER_SELF_DESCRIPTION["version"]["software"]["ssh"] = "?"
        try:
            self.CONTAINER_SELF_DESCRIPTION["version"]["software"]["rsync"] = (
                subprocess.run(
                    ["rsync", "--version"], capture_output=True, text=True,
                    check=True
                ).stdout.split("\n")[0]
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            self.CONTAINER_SELF_DESCRIPTION["version"]["software"]["rsync"] = "?"

        # configuration
        settings = self.CONTAINER_SELF_DESCRIPTION["configuration"]["settings"]
        settings["transfer"] = {
            "local": self.LOCAL_TRANSFER,
            "destination": str(self.REMOTE_DESTINATION),
            "overwrite_existing": self.OVERWRITE_EXISTING,
            "validate_checksums": self.VALIDATE_CHECKSUMS,
            "ssh": {
                "host": self.SSH_HOSTNAME,
                "user": self.SSH_USERNAME,
                "identity": str(self.SSH_IDENTITY_FILE),
                "port": str(self.SSH_PORT),
                "batch_mode": self.SSH_BATCH_MODE,
                "options": self.SSH_CLIENT_OPTIONS,
            },
            "rsync": {
                "compression": {
                    "level": self.COMPRESSION_LEVEL,
                },
                "timeout": {
                    "duration": self.TRANSFER_TIMEOUT,
                },
                "retry": {
                    "max_retries": self.TRANSFER_RETRIES,
                    "retry_interval": self.TRANSFER_RETRY_INTERVAL,
                },
                "options": self.TRANSFER_OPTIONS,
            }
        }
        if self.SSH_HOST_PUBLIC_KEY is not None:
            settings["transfer"]["ssh"]["host_key"] = self.SSH_HOST_PUBLIC_KEY
        if self.SSH_HOST_PUBLIC_KEY_ALGORITHM is not None:
            settings["transfer"]["ssh"]["host_key"] = (
                self.SSH_HOST_PUBLIC_KEY_ALGORITHM
            )

"""
Transfer View-class definition
"""

from typing import Optional
import os
from pathlib import Path
import tempfile
import io
from time import sleep
from uuid import uuid4

from flask import Blueprint, jsonify, Response, request
from data_plumber_http.decorators import flask_handler, flask_args, flask_json
from dcm_common import LoggingContext as Context
from dcm_common.orchestra import JobConfig, JobContext, JobInfo
from dcm_common import services

from dcm_transfer_module.config import AppConfig
from dcm_transfer_module.handlers import get_transfer_handler
from dcm_transfer_module.models import TransferConfig, Report
from dcm_transfer_module.components import (
    RsyncParser,
    SSHClient,
    TransferManager,
)


class TransferView(services.OrchestratedView):
    """View-class for sip-transfer."""

    NAME = "transfer"

    def __init__(self, config: AppConfig, *args, **kwargs) -> None:
        super().__init__(config, *args, **kwargs)

        # validate config
        if (self.config.SSH_HOST_PUBLIC_KEY is not None) != (
            self.config.SSH_HOST_PUBLIC_KEY_ALGORITHM is not None
        ):
            raise RuntimeError(
                "Either none or both of `SSH_HOST_PUBLIC_KEY` and "
                "`SSH_HOST_PUBLIC_KEY_ALGORITHM` must be set in config."
            )
        self.parser = RsyncParser()
        self.ssh_client = (
            None
            if self.config.LOCAL_TRANSFER
            else SSHClient(
                host=self.config.SSH_HOSTNAME,
                user=self.config.SSH_USERNAME,
                port=self.config.SSH_PORT,
                identity_file=self.config.SSH_IDENTITY_FILE.resolve(),
                fingerprint=(
                    (
                        self.config.SSH_HOST_PUBLIC_KEY_ALGORITHM,
                        self.config.SSH_HOST_PUBLIC_KEY,
                    )
                    if self.config.SSH_HOST_PUBLIC_KEY is not None
                    else None
                ),
                batch_mode=self.config.SSH_BATCH_MODE,
                default_options=(
                    self.config.SSH_CLIENT_DEFAULT_OPTIONS
                    + self.config.SSH_CLIENT_OPTIONS
                ),
            )
        )
        self.transfer_manager = TransferManager(
            self.ssh_client,
            default_options=(
                self.config.TRANSFER_DEFAULT_OPTIONS
                + self.config.TRANSFER_OPTIONS
            ),
        )

    def register_job_types(self):
        self.config.worker_pool.register_job_type(
            self.NAME, self.transfer, Report
        )

    def configure_bp(self, bp: Blueprint, *args, **kwargs) -> None:
        @bp.route("/transfer", methods=["POST"])
        @flask_handler(  # unknown query
            handler=services.no_args_handler,
            json=flask_args,
        )
        @flask_handler(  # process transfer
            handler=get_transfer_handler(self.config.FS_MOUNT_POINT),
            json=flask_json,
        )
        def transfer(
            transfer: TransferConfig,
            token: Optional[str] = None,
            callback_url: Optional[str] = None,
        ):
            """Submit SIP for transfer to remote system."""
            try:
                token = self.config.controller.queue_push(
                    token or str(uuid4()),
                    JobInfo(
                        JobConfig(
                            self.NAME,
                            original_body=request.json,
                            request_body={
                                "transfer": transfer.json,
                                "callback_url": callback_url,
                            },
                        ),
                        report=Report(
                            host=request.host_url, args=request.json
                        ),
                    ),
                )
            # pylint: disable=broad-exception-caught
            except Exception as exc_info:
                return Response(
                    f"Submission rejected: {exc_info}",
                    mimetype="text/plain",
                    status=500,
                )

            return jsonify(token.json), 201

        self._register_abort_job(bp, "/transfer")

    def transfer(self, context: JobContext, info: JobInfo):
        """Job instructions for the '/transfer' endpoint."""
        os.chdir(self.config.FS_MOUNT_POINT)
        transfer_config = TransferConfig.from_json(
            info.config.request_body["transfer"]
        )
        info.report.log.set_default_origin("Transfer Module")

        # set progress info
        info.report.progress.verbose = "testing SSH-connection to remote" + (
            ""
            if self.config.LOCAL_TRANSFER
            else f" at '{self.ssh_client.destination}'"
        )
        context.push()

        # check connection to remote
        if not self.config.LOCAL_TRANSFER:
            query = self.ssh_client.query_remote("echo 'ok'")
            if query.returncode != 0:
                # abort job
                info.report.data.success = False
                info.report.log.log(
                    Context.ERROR,
                    body="Unable to establish connection to remote ("
                    + query.stderr.replace("\n", "")
                    + "). Aborting..",
                )
                context.push()
                # make callback; rely on _run_callback to push progress-update
                info.report.progress.complete()
                self._run_callback(
                    context, info, info.config.request_body.get("callback_url")
                )
                return

        # if ran locally, create output directory
        if self.config.LOCAL_TRANSFER:
            self.config.REMOTE_DESTINATION.mkdir(parents=True, exist_ok=True)

        # Check for existence of output in destination
        target_dst = (
            self.config.REMOTE_DESTINATION / transfer_config.target.path.name
        )
        info.report.progress.verbose = (
            f"checking availability of target destination '{target_dst}'"
        )
        context.push()
        if self.transfer_manager.dir_exists(target_dst):
            if not self.config.OVERWRITE_EXISTING:
                # stop transfer if the target directory is present
                info.report.data.success = False
                info.report.log.log(
                    Context.ERROR,
                    body="SIP transfer cannot be executed. "
                    + f"The target destination '{target_dst}' already exists.",
                )
                context.push()
                # make callback; rely on _run_callback to push progress-update
                info.report.progress.complete()
                self._run_callback(
                    context, info, info.config.request_body.get("callback_url")
                )
                return
            rm_status, _, rm_stderr = self.transfer_manager.rm(target_dst)
            if rm_status != 0:
                # stop transfer if the target directory is present and
                # cannot be deleted
                info.report.data.success = False
                info.report.log.log(
                    Context.ERROR,
                    origin="Transfer Manager",
                    body=f"Conflicting transfer destination '{target_dst}'. "
                    + "Problem encountered while trying to delete: "
                    + f"{rm_stderr}",
                )
                context.push()
                # make callback; rely on _run_callback to push progress-update
                info.report.progress.complete()
                self._run_callback(
                    context, info, info.config.request_body.get("callback_url")
                )
                return
            # warn and continue
            info.report.log.log(
                Context.WARNING,
                body=f"Conflicting transfer destination '{target_dst}' has "
                + "been deleted.",
            )
            context.push()

        # set progress info
        info.report.progress.verbose = (
            f"preparing transfer of SIP '{transfer_config.target.path}'"
        )
        context.push()

        # create fifo
        fifo = Path(tempfile.mkdtemp()) / info.report.token.value
        os.mkfifo(fifo)

        # register parser and open fifo
        self.parser.listen(fifo, info.report.progress, context.push)
        progress_file = io.open(  # pylint: disable=consider-using-with
            fifo, "w", encoding="utf-8"
        )

        # start transfer
        info.report.progress.verbose = (
            f"transferring SIP '{transfer_config.target.path}'"
        )
        info.report.log.log(
            Context.EVENT,
            body=f"Attempting transfer of SIP '{transfer_config.target.path}'.",
        )
        context.push()
        for retry in range(1 + self.config.TRANSFER_RETRIES):
            # attempt transfer
            tm_log = self.transfer_manager.transfer(
                src=transfer_config.target.path,
                dst=target_dst,
                transfer_timeout=self.config.TRANSFER_TIMEOUT,
                progress_file=progress_file,
                use_compression=self.config.USE_COMPRESSION,
                compression_level=self.config.COMPRESSION_LEVEL,
                validate_checksums=self.config.VALIDATE_CHECKSUMS,
                mirror=True,
                partial=self.config.TRANSFER_RETRIES > 0,
                resume=self.config.TRANSFER_RETRIES > 0,
                bwlimit=self.config.BW_LIMIT,
            )
            # eval results and merge into main log
            info.report.log.merge(tm_log)
            context.push()

            if Context.ERROR not in tm_log:
                break
            if retry < self.config.TRANSFER_RETRIES:
                info.report.log.log(
                    Context.EVENT,
                    body="SIP transfer attempt failed, "
                    + f"retrying in {self.config.TRANSFER_RETRY_INTERVAL}s..",
                )
                context.push()
                sleep(self.config.TRANSFER_RETRY_INTERVAL)

        info.report.progress.verbose = "cleaning up"
        context.push()

        # close fifo
        progress_file.close()

        # evaluate results
        if Context.ERROR not in info.report.log:
            info.report.data.success = True
            info.report.log.log(Context.INFO, body="SIP transfer complete.")
            context.push()
            # make callback; rely on _run_callback to push progress-update
            info.report.progress.complete()
            self._run_callback(
                context, info, info.config.request_body.get("callback_url")
            )
            return
        info.report.data.success = False
        info.report.log.log(Context.ERROR, body="SIP transfer failed.")
        context.push()

        # make callback; rely on _run_callback to push progress-update
        info.report.progress.complete()
        self._run_callback(
            context, info, info.config.request_body.get("callback_url")
        )

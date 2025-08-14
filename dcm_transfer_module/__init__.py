"""
- DCM Transfer Module -
This flask app implements the 'Transfer Module'-API (see
`openapi.yaml` in the sibling-package `dcm_transfer_module_api`).
"""

from typing import Optional
from time import time, sleep

from flask import Flask
from dcm_common.db import KeyValueStoreAdapter
from dcm_common.orchestration import (
    ScalableOrchestrator, get_orchestration_controls
)
from dcm_common.services import DefaultView, ReportView
from dcm_common.services import extensions

from dcm_transfer_module.config import AppConfig
from dcm_transfer_module.views import TransferView
from dcm_transfer_module.models import Report


def app_factory(
    config: AppConfig,
    queue: Optional[KeyValueStoreAdapter] = None,
    registry: Optional[KeyValueStoreAdapter] = None,
    as_process: bool = False,
    block: bool = False,
):
    """
    Returns a flask-app-object.

    config -- app config derived from `AppConfig`
    queue -- queue adapter override
             (default None; use `MemoryStore`)
    registry -- registry adapter override
                (default None; use `MemoryStore`)
    as_process -- whether the app is intended to be run as process via
                  `app.run`; if `True`, startup tasks like starting
                  orchestration-daemon are prepended to `app.run`
                  instead of being run when this factory is executed
                  (default False)
    block -- whether to block execution until all extensions are ready
            (up to 10 seconds); only relevant if not `as_process`
            (default False)
    """

    app = Flask(__name__)
    app.config.from_object(config)

    # create Orchestrator and OrchestratedView-class
    orchestrator = ScalableOrchestrator(
        queue=queue or config.queue,
        registry=registry or config.registry,
        nprocesses=config.ORCHESTRATION_PROCESSES,
    )
    view = TransferView(
        config=config,
        report_type=Report,
        orchestrator=orchestrator,
        context=TransferView.NAME
    )

    # register extensions
    if config.ALLOW_CORS:
        extensions.cors(app)
    notifications_loader = extensions.notifications_loader(
        app, config, as_process
    )
    orchestrator_loader = extensions.orchestration_loader(
        app,
        config,
        orchestrator,
        "Transfer Module",
        as_process,
        [
            extensions.ExtensionEventRequirement(
                notifications_loader.ready,
                "connection to notification-service",
            )
        ],
    )

    def ready():
        """Define condition for readiness."""
        return (
            not config.ORCHESTRATION_AT_STARTUP
            or orchestrator_loader.ready.is_set()
        )

    # block until ready
    if block and not as_process:
        time0 = time()
        while not ready() and time() - time0 < 10:
            sleep(0.01)

    # register orchestrator-controls blueprint
    if getattr(config, "TESTING", False) or config.ORCHESTRATION_CONTROLS_API:
        app.register_blueprint(
            get_orchestration_controls(
                orchestrator,
                orchestrator_loader.data,
                orchestrator_settings={
                    "cwd": config.FS_MOUNT_POINT,
                    "interval": config.ORCHESTRATION_ORCHESTRATOR_INTERVAL,
                },
                daemon_settings={
                    "interval": config.ORCHESTRATION_DAEMON_INTERVAL,
                }
            ),
            url_prefix="/"
        )

    # register blueprints
    app.register_blueprint(
        DefaultView(config, ready=ready).get_blueprint(),
        url_prefix="/"
    )
    app.register_blueprint(
        view.get_blueprint(),
        url_prefix="/"
    )
    app.register_blueprint(
        ReportView(config, orchestrator).get_blueprint(),
        url_prefix="/"
    )

    return app

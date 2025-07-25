"""
- DCM Transfer Module -
This flask app implements the 'Transfer Module'-API (see
`openapi.yaml` in the sibling-package `dcm_transfer_module_api`).
"""

from typing import Optional

from flask import Flask
from dcm_common.db import KeyValueStoreAdapter
from dcm_common.orchestration import (
    ScalableOrchestrator, orchestrator_controls_bp
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
    as_process: bool = False
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
    orchestratord = extensions.orchestration(
        app, config, orchestrator, "Transfer Module", as_process
    )
    extensions.notification(app, config, as_process)

    # register orchestrator-controls blueprint
    if getattr(config, "TESTING", False) or config.ORCHESTRATION_CONTROLS_API:
        app.register_blueprint(
            orchestrator_controls_bp(
                orchestrator, orchestratord,
                default_orchestrator_settings={
                    "cwd": config.FS_MOUNT_POINT,
                    "interval": config.ORCHESTRATION_ORCHESTRATOR_INTERVAL,
                },
                default_daemon_settings={
                    "interval": config.ORCHESTRATION_DAEMON_INTERVAL,
                }
            ),
            url_prefix="/"
        )

    # register blueprints
    app.register_blueprint(
        DefaultView(config, orchestrator).get_blueprint(),
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

from unittest.mock import patch

from artemis.runtime import tray_launcher


def test_launcher_logging_uses_per_port_file(tmp_path):
    log_path = tmp_path / "tray-8009.log"
    with (
        patch.object(tray_launcher, "launcher_log_path", return_value=log_path),
        patch.object(tray_launcher.logging, "basicConfig") as configure,
    ):
        logger = tray_launcher._configure_launcher_logging(8009)
    assert logger.name == "artemis.runtime.tray_launcher"
    configure.assert_called_once()
    assert configure.call_args.kwargs["filename"] == log_path

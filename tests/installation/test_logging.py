import logging

from installer.logging.setup import get_logger, redact, register_secret


def test_secret_redaction(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    register_secret("hunter2")
    assert redact("password=hunter2 ok") == "password=[REDACTED] ok"
    logger = get_logger()
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    logger.info("user typed hunter2")


def test_logger_file_created(tmp_path, monkeypatch, caplog):
    monkeypatch.chdir(tmp_path)
    register_secret("")
    log = get_logger("test-logger-1")
    with caplog.at_level(logging.INFO):
        log.propagate = True
        log.info("hello %s", "world")
        log.propagate = False
    assert "hello world" in caplog.text

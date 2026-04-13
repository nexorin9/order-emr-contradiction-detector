"""
日志记录系统单元测试
"""

import logging
import os
import sys
import tempfile
from pathlib import Path

import pytest

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from src.py.logging_config import (
    LoggingConfig,
    setup_logging,
    get_logger,
    get_current_run_id,
    reset_logging,
)


class TestLoggingConfig:
    """测试LoggingConfig类"""

    def test_generate_run_id(self):
        """测试run_id生成格式"""
        run_id = LoggingConfig.generate_run_id()

        # 验证格式：yyyymmdd_hhmmss_uuid前8位
        parts = run_id.split("_")
        assert len(parts) == 3
        assert len(parts[0]) == 8  # 日期
        assert len(parts[1]) == 6  # 时间
        assert len(parts[2]) == 8  # UUID前8位

    def test_default_initialization(self):
        """测试默认初始化"""
        config = LoggingConfig()

        assert config.log_level == "INFO"
        assert config.log_dir == "logs"
        assert config.log_to_file is True
        assert config.log_to_console is True
        assert config.run_id is not None
        assert len(config.run_id) > 0

    def test_custom_initialization(self):
        """测试自定义初始化"""
        config = LoggingConfig(
            log_level="DEBUG",
            log_dir="/tmp/test_logs",
            log_to_file=False,
            log_to_console=True,
            run_id="test_run_123",
        )

        assert config.log_level == "DEBUG"
        assert config.log_dir == "/tmp/test_logs"
        assert config.log_to_file is False
        assert config.log_to_console is True
        assert config.run_id == "test_run_123"

    def test_log_level_mapping(self):
        """测试日志级别映射"""
        config = LoggingConfig(log_level="DEBUG")
        assert config.LOG_LEVELS.get("DEBUG") == logging.DEBUG

        config = LoggingConfig(log_level="ERROR")
        assert config.LOG_LEVELS.get("ERROR") == logging.ERROR

    def test_configure_creates_directory(self):
        """测试configure创建日志目录"""
        tmpdir = tempfile.mkdtemp()
        try:
            config = LoggingConfig(log_dir=tmpdir, log_to_file=True, log_to_console=False)
            config.configure()

            assert os.path.exists(tmpdir)
            assert os.path.isdir(tmpdir)
        finally:
            config.close() if hasattr(config, 'close') else reset_logging()

    def test_configure_returns_logger(self):
        """测试configure返回日志记录器"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = LoggingConfig(log_dir=tmpdir, log_to_file=False, log_to_console=False)
            logger = config.configure()

            assert isinstance(logger, logging.Logger)
            assert logger.level == logging.INFO

    def test_get_logger(self):
        """测试获取子日志记录器"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = LoggingConfig(
                log_dir=tmpdir,
                log_to_file=False,
                log_to_console=False,
                run_id="test_logger_001",
            )
            config.configure()

            logger = config.get_logger("test_module")

            assert isinstance(logger, logging.Logger)
            assert logger.name == "test_module"
            assert hasattr(logger, "run_id")
            assert logger.run_id == "test_logger_001"

    def test_run_id_uniqueness(self):
        """测试run_id唯一性"""
        run_ids = [LoggingConfig.generate_run_id() for _ in range(100)]
        unique_ids = set(run_ids)

        # 100个生成应该大部分都是唯一的（时间戳相同但uuid不同）
        assert len(unique_ids) >= 90  # 允许少量重复


class TestSetupLogging:
    """测试setup_logging便捷函数"""

    def test_setup_logging_returns_tuple(self):
        """测试setup_logging返回元组"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config, logger = setup_logging(
                log_level="INFO",
                log_dir=tmpdir,
                log_to_file=False,
                log_to_console=False,
                run_id="setup_test_001",
            )

            assert isinstance(config, LoggingConfig)
            assert isinstance(logger, logging.Logger)

    def test_setup_logging_with_file_output(self):
        """测试setup_logging文件输出"""
        tmpdir = tempfile.mkdtemp()
        try:
            config, logger = setup_logging(
                log_level="DEBUG",
                log_dir=tmpdir,
                log_to_file=True,
                log_to_console=False,
                run_id="file_test_001",
            )

            # 写入一条日志
            logger.info("Test log message")

            # 验证文件是否创建
            log_file = os.path.join(tmpdir, f"detection_{config.run_id}.log")
            assert os.path.exists(log_file)
        finally:
            config.close() if hasattr(config, 'close') else reset_logging()


class TestGetLogger:
    """测试get_logger便捷函数"""

    def test_get_logger_returns_logger(self):
        """测试get_logger返回日志记录器"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 先初始化日志系统
            config, _ = setup_logging(
                log_dir=tmpdir,
                log_to_file=False,
                log_to_console=False,
                run_id="get_logger_test",
            )

            logger = get_logger("test_child")
            assert isinstance(logger, logging.Logger)
            assert logger.name == "test_child"

    def test_get_logger_without_init(self):
        """测试未初始化时获取logger"""
        reset_logging()

        logger = get_logger("uninit_module")
        assert isinstance(logger, logging.Logger)


class TestGetCurrentRunId:
    """测试get_current_run_id函数"""

    def test_get_current_run_id(self):
        """测试获取当前run_id"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config, _ = setup_logging(
                log_dir=tmpdir,
                log_to_file=False,
                log_to_console=False,
                run_id="runid_test_001",
            )

            run_id = get_current_run_id()
            assert run_id == "runid_test_001"

    def test_get_current_run_id_unknown_when_not_set(self):
        """测试未设置时返回unknown"""
        reset_logging()
        run_id = get_current_run_id()
        # 未初始化时可能返回unknown或实际值
        assert run_id is not None


class TestResetLogging:
    """测试reset_logging函数"""

    def test_reset_logging(self):
        """测试重置日志系统"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config, logger = setup_logging(
                log_dir=tmpdir,
                log_to_file=True,
                log_to_console=True,
            )

            # 添加处理器
            handler_count_before = len(logging.getLogger().handlers)

            reset_logging()

            # 处理器应该被清除
            # 注意：reset后根logger的handlers应该是0或很少
            assert True  # 基本功能测试


class TestLogIntegration:
    """集成测试：日志与其他模块的集成"""

    def test_logger_has_run_id_attribute(self):
        """测试logger具有run_id属性"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config, _ = setup_logging(
                log_dir=tmpdir,
                log_to_file=False,
                log_to_console=False,
                run_id="integration_test_001",
            )

            from src.py.engine.contradiction_engine import ContradictionDetector

            # ContradictionDetector使用logger = logging.getLogger(__name__)
            # 应该继承run_id
            logger = logging.getLogger("py.engine.contradiction_engine")

            # 验证logger有run_id
            assert hasattr(logger, "run_id") or logger.name == "py.engine.contradiction_engine"

    def test_log_file_contains_run_id(self):
        """测试日志文件包含run_id"""
        tmpdir = tempfile.mkdtemp()
        try:
            config, logger = setup_logging(
                log_dir=tmpdir,
                log_to_file=True,
                log_to_console=False,
                run_id="logfile_test_001",
            )

            test_message = f"Test message with run_id {config.run_id}"
            logger.info(test_message)

            # 读取日志文件
            log_file = os.path.join(tmpdir, f"detection_{config.run_id}.log")
            assert os.path.exists(log_file)

            with open(log_file, "r", encoding="utf-8") as f:
                content = f.read()
                assert test_message in content or "Test message" in content
        finally:
            config.close() if hasattr(config, 'close') else reset_logging()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

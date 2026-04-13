"""
日志记录系统配置模块

核心功能：
1. 配置日志级别（DEBUG/INFO/WARNING/ERROR）
2. 日志同时输出到文件（logs/detection.log）和控制台
3. 每个检测run生成独立日志文件（含时间戳）
4. 日志包含run_id方便追踪
"""

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional


class RunIdFilter(logging.Filter):
    """日志过滤器，添加run_id到每条日志记录"""

    def __init__(self, run_id: str):
        super().__init__()
        self.run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = self.run_id
        return True


class MultiFileHandler(logging.FileHandler):
    """复合文件处理器，同时写入独立日志文件和主日志文件"""

    def __init__(self, filename: str, mode: str, encoding: str, run_id: str, log_dir: str):
        super().__init__(filename, mode, encoding)
        self.run_id = run_id
        self.log_dir = log_dir
        # 主日志文件路径
        self.main_log_path = os.path.join(log_dir, "detection.log")

    def emit(self, record):
        try:
            # 先调用父类的emit写入独立日志文件
            super().emit(record)
            # 再写入主日志文件
            self._emit_to_main_log(record)
        except Exception:
            # 避免日志系统本身的错误导致程序崩溃
            self.handleError(record)

    def _emit_to_main_log(self, record: logging.LogRecord):
        """写入主日志文件"""
        try:
            with open(self.main_log_path, "a", encoding="utf-8") as f:
                # 格式化记录
                msg = self.format(record)
                f.write(msg + "\n")
        except Exception:
            pass


class LoggingConfig:
    """日志配置类

    提供统一的日志配置和管理功能。
    """

    # 默认日志格式
    DEFAULT_FORMAT = "%(asctime)s - %(name)s - [%(run_id)s] - %(levelname)s - %(message)s"
    DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    # 日志级别映射
    LOG_LEVELS = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    def __init__(
        self,
        log_level: str = "INFO",
        log_dir: str = "logs",
        log_to_file: bool = True,
        log_to_console: bool = True,
        run_id: Optional[str] = None,
    ):
        """初始化日志配置

        Args:
            log_level: 日志级别（DEBUG/INFO/WARNING/ERROR）
            log_dir: 日志文件目录
            log_to_file: 是否输出到文件
            log_to_console: 是否输出到控制台
            run_id: 运行ID（若为None则自动生成）
        """
        self.log_level = log_level.upper()
        self.log_dir = log_dir
        self.log_to_file = log_to_file
        self.log_to_console = log_to_console
        self.run_id = run_id or self.generate_run_id()
        self._root_logger: Optional[logging.Logger] = None
        self._handlers: List[logging.Handler] = []

    @staticmethod
    def generate_run_id() -> str:
        """生成唯一的运行ID

        Returns:
            格式为 yyyymmdd_hhmmss_uuid前8位 的运行ID
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        return f"{timestamp}_{unique_id}"

    def _create_log_dir(self) -> None:
        """创建日志目录（如果不存在）"""
        if self.log_to_file:
            Path(self.log_dir).mkdir(parents=True, exist_ok=True)

    def _get_file_handler(self) -> MultiFileHandler:
        """创建文件日志处理器

        Returns:
            MultiFileHandler对象
        """
        # 每个run生成独立的日志文件
        log_filename = f"detection_{self.run_id}.log"
        log_filepath = os.path.join(self.log_dir, log_filename)

        handler = MultiFileHandler(
            log_filepath,
            mode="a",
            encoding="utf-8",
            run_id=self.run_id,
            log_dir=self.log_dir,
        )
        return handler

    def _get_console_handler(self) -> logging.StreamHandler:
        """创建控制台日志处理器

        Returns:
            StreamHandler对象
        """
        handler = logging.StreamHandler()
        handler.setLevel(self.LOG_LEVELS.get(self.log_level, logging.INFO))
        return handler

    def _create_formatter(self) -> logging.Formatter:
        """创建日志格式化器

        Returns:
            Formatter对象
        """
        formatter = logging.Formatter(
            self.DEFAULT_FORMAT,
            datefmt=self.DEFAULT_DATE_FORMAT
        )
        return formatter

    def _create_filter(self) -> RunIdFilter:
        """创建run_id过滤器

        Returns:
            RunIdFilter对象
        """
        return RunIdFilter(self.run_id)

    def configure(self) -> logging.Logger:
        """配置日志系统

        Returns:
            配置好的根日志记录器
        """
        self._create_log_dir()

        # 获取根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(self.LOG_LEVELS.get(self.log_level, logging.INFO))

        # 清除现有处理器
        root_logger.handlers.clear()
        self._handlers.clear()

        # 创建格式化器和过滤器
        formatter = self._create_formatter()
        run_id_filter = self._create_filter()

        # 添加文件处理器
        if self.log_to_file:
            file_handler = self._get_file_handler()
            file_handler.setFormatter(formatter)
            file_handler.addFilter(run_id_filter)
            root_logger.addHandler(file_handler)
            self._handlers.append(file_handler)

        # 添加控制台处理器
        if self.log_to_console:
            console_handler = self._get_console_handler()
            console_handler.setFormatter(formatter)
            console_handler.addFilter(run_id_filter)
            root_logger.addHandler(console_handler)
            self._handlers.append(console_handler)

        # 在根logger上设置run_id属性
        root_logger.run_id = self.run_id

        self._root_logger = root_logger

        root_logger.info(f"日志系统初始化完成，run_id: {self.run_id}")
        return root_logger

    def get_logger(self, name: str) -> logging.Logger:
        """获取指定名称的日志记录器

        Args:
            name: 日志记录器名称（通常使用__name__）

        Returns:
            日志记录器对象
        """
        if self._root_logger is None:
            self.configure()

        logger = logging.getLogger(name)

        # 确保子logger继承run_id属性
        if not hasattr(logger, 'run_id'):
            logger.run_id = self.run_id

        return logger

    def close(self):
        """关闭所有处理器"""
        for handler in self._handlers:
            handler.close()


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = "logs",
    log_to_file: bool = True,
    log_to_console: bool = True,
    run_id: Optional[str] = None,
) -> tuple:
    """设置日志系统的便捷函数

    Args:
        log_level: 日志级别
        log_dir: 日志目录
        log_to_file: 是否输出到文件
        log_to_console: 是否输出到控制台
        run_id: 运行ID

    Returns:
        (LoggingConfig对象, 根日志记录器)
    """
    config = LoggingConfig(
        log_level=log_level,
        log_dir=log_dir,
        log_to_file=log_to_file,
        log_to_console=log_to_console,
        run_id=run_id,
    )
    root_logger = config.configure()
    return config, root_logger


def get_logger(name: str, run_id: Optional[str] = None) -> logging.Logger:
    """获取日志记录器的便捷函数

    如果日志系统未初始化，会使用默认配置初始化。

    Args:
        name: 日志记录器名称
        run_id: 运行ID

    Returns:
        日志记录器对象
    """
    logger = logging.getLogger(name)

    # 如果run_id存在，设置到logger
    if run_id:
        logger.run_id = run_id
    elif not hasattr(logger, 'run_id'):
        # 尝试从根logger获取run_id
        root = logging.getLogger()
        if hasattr(root, 'run_id'):
            logger.run_id = root.run_id
        else:
            logger.run_id = "unknown"

    return logger


def get_current_run_id() -> str:
    """获取当前运行的run_id

    Returns:
        当前run_id，如果不存在则返回"unknown"
    """
    root = logging.getLogger()
    if hasattr(root, 'run_id') and root.run_id is not None:
        return root.run_id
    return "unknown"


def reset_logging() -> None:
    """重置日志系统（清除所有处理器）"""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        handler.close()
        root_logger.removeHandler(handler)
    root_logger.run_id = None

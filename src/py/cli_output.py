"""
CLI输出格式化模块

提供彩色输出的跨平台支持（Windows/Linux/macOS）。
使用colorama实现Windows兼容的ANSI颜色输出。
"""

import sys
from typing import Optional

try:
    from colorama import init, Fore, Style

    # Windows下自动初始化colorama
    init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    # colorama未安装时的降级方案
    COLORAMA_AVAILABLE = False
    # 定义空样式类作为降级
    class _DummyFore:
        RED = ''
        YELLOW = ''
        GREEN = ''
        CYAN = ''
        MAGENTA = ''
        BLUE = ''
        WHITE = ''
        RESET = ''

    class _DummyStyle:
        BRIGHT = ''
        RESET_ALL = ''

    class _DummyModule:
        Fore = _DummyFore()
        Style = _DummyStyle()

    # 为了代码兼容性，创建等价对象
    class _ColorModule:
        RED = ''
        YELLOW = ''
        GREEN = ''
        CYAN = ''
        MAGENTA = ''
        BLUE = ''
        WHITE = ''
        RESET = ''
        BRIGHT = ''
        RESET_ALL = ''

    Fore = _ColorModule()
    Style = _ColorModule()


class CLIOutput:
    """CLI彩色输出格式化类"""

    # 颜色定义
    COLOR_ERROR = Fore.RED if COLORAMA_AVAILABLE else ''
    COLOR_WARNING = Fore.YELLOW if COLORAMA_AVAILABLE else ''
    COLOR_SUCCESS = Fore.GREEN if COLORAMA_AVAILABLE else ''
    COLOR_INFO = Fore.CYAN if COLORAMA_AVAILABLE else ''
    COLOR_DEBUG = Fore.BLUE if COLORAMA_AVAILABLE else ''
    COLOR_HIGHLIGHT = Fore.MAGENTA if COLORAMA_AVAILABLE else ''
    COLOR_RESET = Style.RESET_ALL if COLORAMA_AVAILABLE else ''
    COLOR_BRIGHT = Style.BRIGHT if COLORAMA_AVAILABLE else ''

    @staticmethod
    def error(message: str, suggestion: Optional[str] = None, stderr: bool = True) -> None:
        """输出错误信息（红色）

        Args:
            message: 错误信息
            suggestion: 建议操作（可选）
            stderr: 是否输出到stderr
        """
        full_message = f"{CLIOutput.COLOR_ERROR}{CLIOutput.COLOR_BRIGHT}[错误]{CLIOutput.COLOR_RESET} {message}"
        if suggestion:
            full_message += f"\n{CLIOutput.COLOR_WARNING}  → 建议: {suggestion}{CLIOutput.COLOR_RESET}"

        print(full_message, file=sys.stderr if stderr else sys.stdout)

    @staticmethod
    def warning(message: str, details: Optional[str] = None, stderr: bool = True) -> None:
        """输出警告信息（黄色）

        Args:
            message: 警告信息
            details: 详细说明（可选）
            stderr: 是否输出到stderr
        """
        full_message = f"{CLIOutput.COLOR_WARNING}[警告]{CLIOutput.COLOR_RESET} {message}"
        if details:
            full_message += f"\n{CLIOutput.COLOR_INFO}  ℹ {details}{CLIOutput.COLOR_RESET}"

        print(full_message, file=sys.stderr if stderr else sys.stdout)

    @staticmethod
    def success(message: str, details: Optional[str] = None, stdout: bool = True) -> None:
        """输出成功信息（绿色）

        Args:
            message: 成功信息
            details: 详细说明（可选）
            stdout: 是否输出到stdout
        """
        full_message = f"{CLIOutput.COLOR_SUCCESS}✓ 成功{CLIOutput.COLOR_RESET} {message}"
        if details:
            full_message += f"\n{CLIOutput.COLOR_SUCCESS}  → {details}{CLIOutput.COLOR_RESET}"

        print(full_message, file=sys.stdout if stdout else sys.stderr)

    @staticmethod
    def info(message: str, details: Optional[str] = None) -> None:
        """输出信息（青色）

        Args:
            message: 信息内容
            details: 详细说明（可选）
        """
        full_message = f"{CLIOutput.COLOR_INFO}[信息]{CLIOutput.COLOR_RESET} {message}"
        if details:
            full_message += f"\n{CLIOutput.COLOR_DEBUG}  ℹ {details}{CLIOutput.COLOR_RESET}"

        print(full_message)

    @staticmethod
    def debug(message: str, details: Optional[str] = None) -> None:
        """输出调试信息（蓝色）

        Args:
            message: 调试信息
            details: 详细说明（可选）
        """
        full_message = f"{CLIOutput.COLOR_DEBUG}[调试]{CLIOutput.COLOR_RESET} {message}"
        if details:
            full_message += f"\n  {details}"

        print(full_message)

    @staticmethod
    def step(message: str, step_num: Optional[int] = None) -> None:
        """输出步骤信息

        Args:
            message: 步骤信息
            step_num: 步骤编号（可选）
        """
        if step_num is not None:
            full_message = f"{CLIOutput.COLOR_HIGHLIGHT}[步骤{step_num}]{CLIOutput.COLOR_RESET} {message}"
        else:
            full_message = f"{CLIOutput.COLOR_HIGHLIGHT}▸ {message}{CLIOutput.COLOR_RESET}"

        print(full_message)

    @staticmethod
    def header(message: str) -> None:
        """输出标题信息

        Args:
            message: 标题内容
        """
        separator = "=" * 50
        print(f"\n{CLIOutput.COLOR_BRIGHT}{separator}{CLIOutput.COLOR_RESET}")
        print(f"{CLIOutput.COLOR_BRIGHT}{message}{CLIOutput.COLOR_RESET}")
        print(f"{CLIOutput.COLOR_BRIGHT}{separator}{CLIOutput.COLOR_RESET}\n")

    @staticmethod
    def table(headers: list, rows: list) -> None:
        """输出表格（简单ASCII表格）

        Args:
            headers: 表头列表
            rows: 行数据列表（每行也是列表）
        """
        if not rows:
            return

        # 计算每列的最大宽度
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))

        # 构建表格
        sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
        header_line = "|" + "|".join(f" {h:<{col_widths[i]}} " for i, h in enumerate(headers)) + "|"

        print(sep)
        print(f"{CLIOutput.COLOR_BRIGHT}{header_line}{CLIOutput.COLOR_RESET}")
        print(sep)

        for row in rows:
            row_line = "|" + "|".join(f" {str(cell):<{col_widths[i]}} " for i, cell in enumerate(row)) + "|"
            print(row_line)

        print(sep)


# 全局快捷函数
def cli_error(message: str, suggestion: Optional[str] = None):
    """快捷错误输出"""
    CLIOutput.error(message, suggestion)


def cli_warning(message: str, details: Optional[str] = None):
    """快捷警告输出"""
    CLIOutput.warning(message, details)


def cli_success(message: str, details: Optional[str] = None):
    """快捷成功输出"""
    CLIOutput.success(message, details)


def cli_info(message: str, details: Optional[str] = None):
    """快捷信息输出"""
    CLIOutput.info(message, details)
@echo off
echo 安装 Python 依赖...

cd /d "%~dp0\.."

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未找到 Python，请先安装 Python 3.10+
    exit /b 1
)

:: Check if pip is installed
pip --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未找到 pip，请先安装 pip
    exit /b 1
)

:: Create virtual environment (optional but recommended)
if not exist "venv" (
    echo 创建虚拟环境...
    python -m venv venv
)

:: Activate virtual environment
echo 激活虚拟环境...
call venv\Scripts\activate.bat

:: Upgrade pip
echo 升级 pip...
python -m pip install --upgrade pip

:: Install Python dependencies
echo 安装 Python 包...
pip install -r requirements.txt

echo.
echo Python 依赖安装完成！
echo.
echo 可选：激活虚拟环境
echo   venv\Scripts\activate.bat

@echo off
REM 多运营商套餐监控系统 - 启动脚本

echo.
echo ============================================================
echo 多运营商套餐监控系统 - 网页版
echo ============================================================
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未检测到 Python，请先安装 Python 并添加到环境变量中。
    pause
    exit /b 1
)

REM 切换到项目目录
cd /d "%~dp0"

REM 检查依赖
echo 正在检查并自动安装依赖...
pip install -r requirements.txt -q

echo.
echo 正在启动服务器...
echo.
echo 服务器地址: http://localhost:10000
echo.
echo 按 Ctrl+C 停止服务器
echo.

python app/api_server.py

pause

@echo off
REM 鲨鲨机器人一键部署脚本 (Windows)
REM 使用方法：双击运行 deploy.bat 或在命令行运行

echo ======================================
echo   鲨鲨机器人部署脚本 (Windows)
echo ======================================
echo.

REM 检查 uv
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] uv 未安装，正在安装...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
) else (
    echo [+] uv 已安装
)

REM 检查 Python
python --version >nul 2>nul
if %errorlevel% neq 0 (
    echo [x] Python 未安装，请先安装 Python 3.11+
    pause
    exit /b 1
) else (
    echo [+] Python 已安装
)

REM 安装依赖
echo [!] 安装依赖...
uv sync
echo [+] 依赖安装完成

REM 配置配置文件
if not exist "config\bot_settings.json" (
    echo [!] 创建配置文件...
    copy config\bot_settings.example.json config\bot_settings.json
    echo [+] 配置文件已创建：config\bot_settings.json
    echo [!] 请编辑 config\bot_settings.json 填入你的 API Key
) else (
    echo [+] 配置文件已存在
)

echo.
echo ======================================
echo   部署完成！
echo ======================================
echo.
echo 下一步：
echo   1. 编辑 config\bot_settings.json 填入 API Key
echo   2. 运行：uv run python run_bot.py
echo.
echo 持久运行：
echo   方案 1: 使用 nssm 创建 Windows 服务
echo   方案 2: 使用任务计划程序
echo.
pause

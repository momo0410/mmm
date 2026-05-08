@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

echo ========================================
echo   SDIT 一键启动
echo ========================================
echo.

if not exist "%ROOT_DIR%package.json" (
  echo [错误] 未找到 package.json，请确认脚本位于项目根目录。
  pause
  exit /b 1
)

if not exist "%ROOT_DIR%src-python\run.py" (
  echo [错误] 未找到 src-python\run.py，请确认后端目录完整。
  pause
  exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
  echo [错误] 未找到 node，请先安装 Node.js 并加入 PATH。
  pause
  exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
  echo [错误] 未找到 npm，请先安装 Node.js / npm 并加入 PATH。
  pause
  exit /b 1
)

set "BACKEND_PYTHON="
if exist "%ROOT_DIR%.venv\Scripts\python.exe" (
  set "BACKEND_PYTHON=%ROOT_DIR%.venv\Scripts\python.exe"
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo [错误] 未找到 Python，且项目内也没有 .venv\Scripts\python.exe。
    pause
    exit /b 1
  )
  set "BACKEND_PYTHON=python"
)

echo [信息] 项目目录: %ROOT_DIR%
echo [信息] 后端 Python: %BACKEND_PYTHON%
echo.
echo [启动] 后端服务...
start "SDIT Backend" /D "%ROOT_DIR%src-python" cmd /k "set PY_BACKEND_RELOAD=0 && set PY_BACKEND_PORT=3001 && call \"%BACKEND_PYTHON%\" run.py"

timeout /t 2 /nobreak >nul

echo [启动] 前端服务...
start "SDIT Frontend" /D "%ROOT_DIR%" cmd /k "call npm run dev -- --host 0.0.0.0"

echo.
echo ========================================
echo   已启动前后端
echo ========================================
echo 前端地址: http://127.0.0.1:1420
echo 后端地址: http://127.0.0.1:3001
echo.
echo 已分别在两个命令行窗口中运行。
echo 关闭对应窗口即可停止服务。
echo.
pause

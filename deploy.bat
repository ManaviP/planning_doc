@echo off
REM One-Click Deployment Helper for Windows
REM Usage: deploy.bat [command]
REM Commands: up, down, smoke, gates, clean, help

if "%1%"=="" goto help
if "%1%"=="help" goto help
if "%1%"=="up" goto up
if "%1%"=="down" goto down
if "%1%"=="smoke" goto smoke
if "%1%"=="gates" goto gates
if "%1%"=="clean" goto clean

goto invalid

:help
echo Available commands:
echo   deploy.bat help   - Show this help
echo   deploy.bat up     - Start all services with preflight checks
echo   deploy.bat down   - Stop docker compose services
echo   deploy.bat smoke  - Run end-to-end smoke test
echo   deploy.bat gates  - Run promotion gates locally
echo   deploy.bat clean  - Stop services, remove volumes, delete minikube
exit /b 0

:up
call bash ./start.sh
exit /b %ERRORLEVEL%

:down
docker compose down
exit /b %ERRORLEVEL%

:smoke
python test_smoke.py
exit /b %ERRORLEVEL%

:gates
python backend/promotion/gates.py --api-base-url http://localhost:8000
exit /b %ERRORLEVEL%

:clean
docker compose down -v
minikube delete
exit /b %ERRORLEVEL%

:invalid
echo Unknown command: %1%
echo Run: deploy.bat help
exit /b 1

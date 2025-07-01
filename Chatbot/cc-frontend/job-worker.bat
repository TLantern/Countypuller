@echo off
echo Starting CountyPuller Job Worker...
echo.

REM Set Node.js path
set NODE_PATH=C:\Program Files\nodejs\node.exe
set NPM_PATH=C:\Program Files\nodejs\npm.cmd

REM Check if node exists at the specified path
if not exist "%NODE_PATH%" (
    echo Node.js not found at %NODE_PATH%
    echo Please update the NODE_PATH in this script.
    exit /b 1
)

REM Check if .env file exists
if not exist ".env" (
    echo WARNING: .env file not found!
    echo Please create a .env file with your database configuration.
    echo See .env.example for required variables.
    echo.
)

REM Install dependencies if needed
if not exist "node_modules" (
    echo Installing dependencies...
    call "%NPM_PATH%" install --legacy-peer-deps
    if %ERRORLEVEL% NEQ 0 (
        echo Failed to install dependencies
        exit /b 1
    )
)

REM Start the job worker
echo Starting job worker...
"%NODE_PATH%" start-job-worker.js 
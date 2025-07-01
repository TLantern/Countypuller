@echo off
echo CountyPuller Setup Script
echo =========================
echo.

REM Set Node.js paths
set NODE_PATH=C:\Program Files\nodejs\node.exe
set NPM_PATH=C:\Program Files\nodejs\npm.cmd

REM Check if Node.js exists
if not exist "%NODE_PATH%" (
    echo ERROR: Node.js not found at %NODE_PATH%
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

echo Using Node.js from: %NODE_PATH%
"%NODE_PATH%" --version
echo.

REM Clean up old installations
echo Cleaning up old installations...
if exist "node_modules" (
    echo Removing node_modules...
    rmdir /s /q node_modules 2>nul
)
if exist "package-lock.json" del /f package-lock.json 2>nul
if exist ".next" rmdir /s /q .next 2>nul

REM Install dependencies
echo Installing dependencies...
"%NPM_PATH%" install --legacy-peer-deps
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

REM Check if .env exists
if not exist ".env" (
    echo.
    echo WARNING: .env file not found!
    echo Please create a .env file with your configuration.
    echo Example:
    echo   DATABASE_URL="postgresql://user:password@localhost:5432/dbname"
    echo   NEXTAUTH_SECRET="your-secret-key"
    echo   NEXTAUTH_URL="http://localhost:3000"
    echo.
)

echo.
echo Setup completed successfully!
echo.
echo To start the development server, run: dev.bat
echo To start the job worker, run: job-worker.bat
echo.
pause 
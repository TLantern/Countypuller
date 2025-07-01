@echo off
echo Starting CountyPuller Development Server...
echo.

REM Set Node.js path
set NODE_PATH=C:\Program Files\nodejs\node.exe

REM Check if node exists at the specified path
if not exist "%NODE_PATH%" (
    echo Node.js not found at %NODE_PATH%
    echo Please run setup.bat first.
    pause
    exit /b 1
)

REM Check if node_modules exists
if not exist "node_modules" (
    echo Dependencies not installed!
    echo Please run setup.bat first.
    pause
    exit /b 1
)

REM Check if .env file exists
if not exist ".env" (
    echo WARNING: .env file not found!
    echo Please create a .env file with your database configuration.
    echo.
)

REM Generate Prisma client
if exist "node_modules\.bin\prisma.cmd" (
    echo Generating Prisma client...
    call node_modules\.bin\prisma.cmd generate
    if %ERRORLEVEL% NEQ 0 (
        echo Warning: Failed to generate Prisma client
    )
)

REM Start the development server
echo Starting Next.js development server...
if exist "node_modules\.bin\next.cmd" (
    call node_modules\.bin\next.cmd dev
) else (
    echo ERROR: Next.js not found in node_modules
    echo Please run setup.bat to install dependencies
    pause
    exit /b 1
) 
@echo off
echo Starting Job Worker...

REM Try node command first (if in PATH)
node scripts/job-worker.js 2>nul
if %ERRORLEVEL% == 0 goto :end

REM Try full path to Node.js
"C:\Program Files\nodejs\node.exe" scripts/job-worker.js 2>nul
if %ERRORLEVEL% == 0 goto :end

REM If neither works, show error
echo Error: Node.js not found. Please ensure Node.js is installed.
echo Try running one of these commands directly:
echo   node scripts/job-worker.js
echo   "C:\Program Files\nodejs\node.exe" scripts/job-worker.js
echo   "/c/Program Files/nodejs/node.exe" scripts/job-worker.js  (for Git Bash)

:end 
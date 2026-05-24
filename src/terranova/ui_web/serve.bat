@echo off
REM Terranova web-tier dev server.
REM Use this to iterate on the React panel in a normal browser; QGIS embeds
REM the same bundle via QWebEngineView at runtime.

setlocal
where node >nul 2>nul
if errorlevel 1 (
    echo Node is not installed or not on PATH.
    exit /b 1
)

if not exist node_modules (
    echo Installing dependencies...
    call npm install
    if errorlevel 1 exit /b 1
)

echo Starting Vite dev server on http://localhost:5173 ...
call npm run dev
endlocal

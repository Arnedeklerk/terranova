# Terranova web-tier dev server (PowerShell).
# Iterates on the React panel in a normal browser without QGIS in the loop.

$ErrorActionPreference = "Stop"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error "Node is not installed or not on PATH."
    exit 1
}

if (-not (Test-Path node_modules)) {
    Write-Host "Installing dependencies..."
    npm install
}

Write-Host "Starting Vite dev server on http://localhost:5173 ..."
npm run dev

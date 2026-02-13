# ============================================================
# AgenticCloudDisc - Dev Startup Script
# Starts MCP Server, Orchestrator, and Client UI
# ============================================================

$ROOT = $PSScriptRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AgenticCloudDisc - Dev Environment"    -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- 1. Install dependencies (skipped - already installed) ---
# Uncomment below if you need to reinstall deps after a clean checkout:
#
# Write-Host "[1/5] Checking Python dependencies..." -ForegroundColor Yellow
# Push-Location "$ROOT\mcp-server"
# if (!(Test-Path "venv")) { python -m venv venv }
# & "$ROOT\mcp-server\venv\Scripts\Activate.ps1"
# pip install -q -r requirements.txt 2>$null
# deactivate
# Pop-Location
# Push-Location "$ROOT\agent-orchestrator"
# if (!(Test-Path "venv")) { python -m venv venv }
# & "$ROOT\agent-orchestrator\venv\Scripts\Activate.ps1"
# pip install -q -r requirements.txt 2>$null
# deactivate
# Pop-Location
#
# Write-Host "[2/5] Checking Node dependencies..." -ForegroundColor Yellow
# if (!(Test-Path "$ROOT\client-ui\node_modules")) {
#     Push-Location "$ROOT\client-ui"; npm install; Pop-Location
# }

Write-Host "  Dependencies: using existing venvs + node_modules" -ForegroundColor Green

# --- 3. Start MCP Server (port 9000) ---
Write-Host "[3/5] Starting MCP Server on :9000..." -ForegroundColor Yellow
$mcp = Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$ROOT\mcp-server'; & '$ROOT\mcp-server\venv\Scripts\Activate.ps1'; uvicorn main:app --reload --port 9000"
) -PassThru
Write-Host "  MCP Server PID: $($mcp.Id)" -ForegroundColor Green

# --- 4. Start Orchestrator (port 8000) ---
Write-Host "[4/5] Starting Orchestrator on :8000..." -ForegroundColor Yellow
Start-Sleep -Seconds 2  # let MCP start first
$orch = Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$ROOT\agent-orchestrator'; & '$ROOT\agent-orchestrator\venv\Scripts\Activate.ps1'; `$env:DEV_SKIP_AUTH='true'; `$env:MCP_BASE_URL='http://localhost:9000'; uvicorn main:app --reload --port 8000"
) -PassThru
Write-Host "  Orchestrator PID: $($orch.Id)" -ForegroundColor Green

# --- 5. Start Client UI (port 5173) ---
Write-Host "[5/5] Starting Client UI on :5173..." -ForegroundColor Yellow
Start-Sleep -Seconds 1
$ui = Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$ROOT\client-ui'; npm run dev"
) -PassThru
Write-Host "  Client UI PID: $($ui.Id)" -ForegroundColor Green

# --- Done ---
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  All services starting!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  MCP Server:   http://localhost:9000/health" -ForegroundColor White
Write-Host "  Orchestrator: http://localhost:8000/healthz" -ForegroundColor White
Write-Host "  Client UI:    http://localhost:5173"         -ForegroundColor White
Write-Host ""
Write-Host "  App auth bypassed (DEV_SKIP_AUTH=true)" -ForegroundColor DarkGray
Write-Host "  Azure auth: real SP credentials required" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  To stop: close the 3 PowerShell windows," -ForegroundColor DarkGray
Write-Host "  or run: .\stop-dev.ps1" -ForegroundColor DarkGray
Write-Host ""

# Open browser
Start-Sleep -Seconds 4
Start-Process "http://localhost:5173"

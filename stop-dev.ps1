# ============================================================
# AgenticCloudDisc - Stop all dev services
# ============================================================

Write-Host "Stopping dev services..." -ForegroundColor Yellow

# Kill uvicorn processes (MCP + Orchestrator)
Get-Process -Name "uvicorn" -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match "uvicorn"
} -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# Kill Node/Vite process (Client UI)
Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match "vite"
} -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "Done. All dev services stopped." -ForegroundColor Green

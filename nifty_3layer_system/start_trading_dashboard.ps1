# NIFTY/SENSEX Live Trading Dashboard - One-Click Startup Script
# This script starts the server and opens the browser automatically

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  NIFTY/SENSEX Live Trading Dashboard - Starting...                  " -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# Set the project directory
$PROJECT_DIR = "C:\Users\akash\PycharmProjects\scalping_engine_complete_project\nifty_3layer_system"
Set-Location $PROJECT_DIR

# Activate virtual environment
Write-Host "[1/4] Activating Python virtual environment..." -ForegroundColor Yellow
& "$PROJECT_DIR\.venv\Scripts\Activate.ps1"
Write-Host "      Virtual environment activated!" -ForegroundColor Green
Write-Host ""

# Start the Uvicorn server in background
Write-Host "[2/4] Starting FastAPI server on port 8000..." -ForegroundColor Yellow
$ServerProcess = Start-Process -FilePath "$PROJECT_DIR\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "webapp.app:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info" `
    -WorkingDirectory $PROJECT_DIR `
    -PassThru `
    -WindowStyle Hidden

Write-Host "      Server starting (PID: $($ServerProcess.Id))..." -ForegroundColor Green
Write-Host ""

# Wait for server to be ready
Write-Host "[3/4] Waiting for server to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

$maxRetries = 10
$retryCount = 0
$serverReady = $false

while ($retryCount -lt $maxRetries -and -not $serverReady) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/api/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $serverReady = $true
            Write-Host "      Server is ready and responding!" -ForegroundColor Green
        }
    } catch {
        $retryCount++
        Write-Host "      Waiting... ($retryCount/$maxRetries)" -ForegroundColor Gray
        Start-Sleep -Seconds 1
    }
}

if (-not $serverReady) {
    Write-Host "      Warning: Server might still be starting..." -ForegroundColor Yellow
}
Write-Host ""

# Open browser
Write-Host "[4/4] Opening browser to http://localhost:8000..." -ForegroundColor Yellow
Start-Sleep -Seconds 1
Start-Process "http://localhost:8000"
Write-Host "      Browser opened!" -ForegroundColor Green
Write-Host ""

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  DASHBOARD IS LIVE!                                                 " -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  URL: http://localhost:8000" -ForegroundColor White
Write-Host "  Server PID: $($ServerProcess.Id)" -ForegroundColor White
Write-Host ""
Write-Host "  Features:" -ForegroundColor Yellow
Write-Host "  - Live NIFTY/SENSEX candlestick charts (5-min)" -ForegroundColor White
Write-Host "  - ML-based BUY/SELL signals with confidence" -ForegroundColor White
Write-Host "  - Real-time WebSocket price updates" -ForegroundColor White
Write-Host "  - Auto-refresh every 5 minutes" -ForegroundColor White
Write-Host "  - Entry/Target/Stop Loss levels" -ForegroundColor White
Write-Host ""
Write-Host "  TO STOP THE SERVER:" -ForegroundColor Red
Write-Host "  Press Ctrl+C or close this window" -ForegroundColor White
Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan

# Keep the window open and show server logs
Write-Host ""
Write-Host "Server is running... Press Ctrl+C to stop." -ForegroundColor Yellow
Write-Host ""

# Wait for user to press Ctrl+C
try {
    $ServerProcess.WaitForExit()
} catch {
    Write-Host ""
    Write-Host "Stopping server..." -ForegroundColor Yellow
    Stop-Process -Id $ServerProcess.Id -Force
    Write-Host "Server stopped." -ForegroundColor Green
}

# run_all_tests.ps1 - Run all agent tests
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Running All Agent Tests" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$failed = 0

# MCP Tests
Write-Host "`n[1/3] Testing MCP Agent..." -ForegroundColor Yellow
cd mcp/test-suites
pytest -v --tb=short
if ($LASTEXITCODE -ne 0) { $failed++ }

# Custom Tests
Write-Host "`n[2/3] Testing Custom Agent..." -ForegroundColor Yellow
cd ../../custom/test-suites
pytest -v --tb=short
if ($LASTEXITCODE -ne 0) { $failed++ }

# Generic Tests
Write-Host "`n[3/3] Testing Generic Agent..." -ForegroundColor Yellow
cd ../../generic/test-suites
pytest -v --tb=short
if ($LASTEXITCODE -ne 0) { $failed++ }

# Summary
cd ../..
Write-Host "`n========================================" -ForegroundColor Cyan
if ($failed -eq 0) {
    Write-Host "✅ ALL TESTS PASSED" -ForegroundColor Green
} else {
    Write-Host "❌ $failed agent(s) failed tests" -ForegroundColor Red
}
Write-Host "========================================" -ForegroundColor Cyan

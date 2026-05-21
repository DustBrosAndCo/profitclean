# ProfitClean - Quick File Structure Check
Write-Host "`n=== ProfitClean File Check ===`n" -ForegroundColor Cyan

$errors = 0
$folder = "D:\DBAPP"

if ((Get-Location).Path -eq $folder) {
    Write-Host "✅ In correct directory: $folder" -ForegroundColor Green
} else {
    Write-Host "❌ Wrong directory. Current: $((Get-Location).Path)" -ForegroundColor Red
    Write-Host "   Run: cd D:\DBAPP" -ForegroundColor Yellow
    $errors++
}

if (Test-Path "$folder\app.py") {
    Write-Host "✅ app.py exists" -ForegroundColor Green
} else {
    Write-Host "❌ app.py MISSING" -ForegroundColor Red
    $errors++
}

if (Test-Path "$folder\requirements.txt") {
    Write-Host "✅ requirements.txt exists" -ForegroundColor Green
    $content = Get-Content "$folder\requirements.txt" -Raw
    foreach ($pkg in @("streamlit", "pandas", "bcrypt", "qrcode", "Pillow")) {
        if ($content -match $pkg) {
            Write-Host "   ✅ $pkg found" -ForegroundColor Green
        } else {
            Write-Host "   ❌ $pkg MISSING" -ForegroundColor Red
            $errors++
        }
    }
} else {
    Write-Host "❌ requirements.txt MISSING" -ForegroundColor Red
    $errors++
}

if (Test-Path "$folder\.gitignore") {
    Write-Host "✅ .gitignore exists" -ForegroundColor Green
} else {
    Write-Host "⚠️ .gitignore MISSING (recommended)" -ForegroundColor Yellow
}

if (Test-Path "$folder\static") {
    Write-Host "✅ static folder exists" -ForegroundColor Green
} else {
    Write-Host "⚠️ static folder MISSING (PWA may not work)" -ForegroundColor Yellow
}

Write-Host "`n=== Summary ===" -ForegroundColor Cyan
if ($errors -eq 0) {
    Write-Host "✅ Ready to deploy!" -ForegroundColor Green
} else {
    Write-Host "❌ Found $errors issue(s) to fix" -ForegroundColor Red
}
Write-Host ""

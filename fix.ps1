# Fix Pydantic BaseSettings Issue
# This script only fixes the code files, you deploy separately

Write-Host "🔧 Fixing Pydantic BaseSettings Issue..." -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan

$fixed = 0
$errors = 0

# Step 1: Fix requirements.txt
Write-Host "`n📝 Fixing requirements.txt..." -ForegroundColor Yellow

$requirementsPath = "requirements.txt"
if (Test-Path $requirementsPath) {
    $requirements = Get-Content $requirementsPath
    
    # Check if pydantic-settings is already there
    if ($requirements -notcontains "pydantic-settings==2.1.0") {
        # Add pydantic-settings
        Add-Content -Path $requirementsPath -Value "pydantic-settings==2.1.0"
        Write-Host "✅ Added pydantic-settings==2.1.0 to requirements.txt" -ForegroundColor Green
        $fixed++
    } else {
        Write-Host "✅ pydantic-settings already in requirements.txt" -ForegroundColor Green
    }
} else {
    Write-Host "❌ requirements.txt not found!" -ForegroundColor Red
    $errors++
}

# Step 2: Fix config.py
Write-Host "`n📝 Fixing app/services/config.py..." -ForegroundColor Yellow

$configPath = "app/services/config.py"
if (Test-Path $configPath) {
    # Read current content
    $configContent = Get-Content $configPath -Raw
    
    # Fix the import
    if ($configContent -match "from pydantic import BaseSettings") {
        $configContent = $configContent -replace "from pydantic import BaseSettings", "from pydantic_settings import BaseSettings"
        $configContent | Set-Content $configPath -NoNewline
        Write-Host "✅ Fixed BaseSettings import in config.py" -ForegroundColor Green
        $fixed++
    } elseif ($configContent -match "from pydantic_settings import BaseSettings") {
        Write-Host "✅ BaseSettings import already correct" -ForegroundColor Green
    } else {
        Write-Host "⚠️ No BaseSettings import found in config.py" -ForegroundColor Yellow
    }
} else {
    Write-Host "❌ Could not find $configPath" -ForegroundColor Red
    $errors++
}

# Step 3: Verify the fixes
Write-Host "`n🔍 Verifying fixes..." -ForegroundColor Yellow

if (Test-Path $requirementsPath) {
    Write-Host "📋 Updated requirements.txt:" -ForegroundColor Cyan
    Get-Content $requirementsPath | Where-Object { $_ -match "pydantic" } | ForEach-Object { 
        Write-Host "  $_" -ForegroundColor White 
    }
}

if (Test-Path $configPath) {
    Write-Host "📋 Updated config.py (first 3 lines):" -ForegroundColor Cyan
    (Get-Content $configPath | Select-Object -First 3) | ForEach-Object { 
        Write-Host "  $_" -ForegroundColor White 
    }
}

# Summary
Write-Host "`n📊 Summary:" -ForegroundColor Cyan
Write-Host "============" -ForegroundColor Cyan
if ($errors -eq 0) {
    Write-Host "✅ All fixes applied successfully!" -ForegroundColor Green
    Write-Host "✅ $fixed file(s) were updated" -ForegroundColor Green
    
    Write-Host "`n🚀 Next Steps:" -ForegroundColor Yellow
    Write-Host "1. Rebuild your Docker image:" -ForegroundColor White
    Write-Host "   gcloud builds submit . --tag asia-southeast1-docker.pkg.dev/wtschedulerfrontend/cloud-run-images/crypto-scheduler-dashboard:latest --project=wtschedulerfrontend" -ForegroundColor Gray
    Write-Host "`n2. Deploy to Cloud Run:" -ForegroundColor White
    Write-Host "   gcloud run deploy crypto-scheduler-dashboard --image=asia-southeast1-docker.pkg.dev/wtschedulerfrontend/cloud-run-images/crypto-scheduler-dashboard:latest --region=asia-southeast1 --project=wtschedulerfrontend --allow-unauthenticated" -ForegroundColor Gray
    
} else {
    Write-Host "❌ $errors error(s) occurred during fixing" -ForegroundColor Red
    Write-Host "Please check the files manually" -ForegroundColor Yellow
}

Write-Host "`n🏁 Fix script completed!" -ForegroundColor Green
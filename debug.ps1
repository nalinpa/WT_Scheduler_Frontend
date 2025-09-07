# Debug Wallet API Integration
param(
    [string]$ServiceUrl = "https://crypto-scheduler-dashboard-v44uxlimnq-as.a.run.app"
)

Write-Host "🔍 Debugging Wallet API Integration" -ForegroundColor Cyan
Write-Host "===================================" -ForegroundColor Cyan

Write-Host "Service URL: $ServiceUrl" -ForegroundColor White

# Step 1: Test if the wallet count endpoint exists in your deployed app
Write-Host "`n1. Testing if wallet count endpoint exists..." -ForegroundColor Yellow

try {
    $walletEndpoint = Invoke-RestMethod -Uri "$ServiceUrl/api/wallets/count" -TimeoutSec 15 -ErrorAction Stop
    Write-Host "✅ Wallet count endpoint exists!" -ForegroundColor Green
    Write-Host "   Response: $($walletEndpoint | ConvertTo-Json)" -ForegroundColor White
    
    if ($walletEndpoint.count -eq 174) {
        Write-Host "✅ Correct count detected!" -ForegroundColor Green
    } else {
        Write-Host "⚠️ Count is $($walletEndpoint.count), not 174" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "❌ Wallet count endpoint not found!" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "   This means the new code wasn't deployed properly" -ForegroundColor Yellow
}

# Step 2: Test the original wallet API directly
Write-Host "`n2. Testing original wallet API directly..." -ForegroundColor Yellow

try {
    $originalApi = Invoke-RestMethod -Uri "https://wallet-api-bigquery-qz6f5mkbmq-as.a.run.app/wallets/count" -TimeoutSec 15 -ErrorAction Stop
    Write-Host "✅ Original wallet API works!" -ForegroundColor Green
    Write-Host "   Count: $($originalApi.count)" -ForegroundColor White
    Write-Host "   Full response: $($originalApi | ConvertTo-Json)" -ForegroundColor Gray
    
} catch {
    Write-Host "❌ Original wallet API failed!" -ForegroundColor Red
    Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "   This could be a network/CORS issue" -ForegroundColor Yellow
}

# Step 3: Check current jobs to see what wallet count they're using
Write-Host "`n3. Checking current jobs..." -ForegroundColor Yellow

try {
    $jobs = Invoke-RestMethod -Uri "$ServiceUrl/api/jobs" -TimeoutSec 10 -ErrorAction Stop
    Write-Host "✅ Found $($jobs.Count) jobs" -ForegroundColor Green
    
    if ($jobs.Count -gt 0) {
        Write-Host "📋 Job details:" -ForegroundColor Cyan
        foreach ($job in $jobs) {
            Write-Host "   - $($job.name): $($job.state)" -ForegroundColor White
        }
    }
    
} catch {
    Write-Host "⚠️ Could not get jobs: $($_.Exception.Message)" -ForegroundColor Yellow
}

# Step 4: Check the status endpoint
Write-Host "`n4. Checking status endpoint..." -ForegroundColor Yellow

try {
    $status = Invoke-RestMethod -Uri "$ServiceUrl/api/status" -TimeoutSec 10 -ErrorAction Stop
    Write-Host "✅ Status endpoint works!" -ForegroundColor Green
    Write-Host "   Response: $($status | ConvertTo-Json)" -ForegroundColor White
    
    if ($status.PSObject.Properties.Name -contains "wallet_count") {
        Write-Host "✅ Status includes wallet_count: $($status.wallet_count)" -ForegroundColor Green
        Write-Host "   Source: $($status.wallet_count_source)" -ForegroundColor White
        Write-Host "   Success: $($status.wallet_count_success)" -ForegroundColor White
    } else {
        Write-Host "❌ Status doesn't include wallet_count (old version deployed)" -ForegroundColor Red
    }
    
} catch {
    Write-Host "❌ Status endpoint failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Step 5: Check the dashboard HTML to see if it has the new features
Write-Host "`n5. Checking dashboard HTML..." -ForegroundColor Yellow

try {
    $dashboard = Invoke-WebRequest -Uri $ServiceUrl -TimeoutSec 10 -ErrorAction Stop
    
    if ($dashboard.Content -match "wallet-count-card") {
        Write-Host "✅ Dashboard has new wallet count UI" -ForegroundColor Green
    } else {
        Write-Host "❌ Dashboard missing new wallet count UI (old version)" -ForegroundColor Red
    }
    
    if ($dashboard.Content -match "refreshWalletCount") {
        Write-Host "✅ Dashboard has wallet refresh function" -ForegroundColor Green
    } else {
        Write-Host "❌ Dashboard missing wallet refresh function (old version)" -ForegroundColor Red
    }
    
} catch {
    Write-Host "❌ Dashboard check failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Step 6: Test job templates
Write-Host "`n6. Testing job templates..." -ForegroundColor Yellow

try {
    $templates = Invoke-RestMethod -Uri "$ServiceUrl/api/job-templates" -TimeoutSec 10 -ErrorAction Stop
    Write-Host "✅ Job templates endpoint works!" -ForegroundColor Green
    
    if ($templates.PSObject.Properties.Name -contains "max_wallets") {
        Write-Host "✅ Templates include max_wallets: $($templates.max_wallets)" -ForegroundColor Green
        Write-Host "   Source: $($templates.wallet_source)" -ForegroundColor White
    } else {
        Write-Host "❌ Templates don't include max_wallets (old version)" -ForegroundColor Red
    }
    
} catch {
    Write-Host "❌ Job templates failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Step 7: Summary and recommendations
Write-Host "`n📊 Summary:" -ForegroundColor Cyan
Write-Host "==========" -ForegroundColor Cyan

$hasNewEndpoint = $false
$hasNewUI = $false
$originalApiWorks = $false

try {
    Invoke-RestMethod -Uri "$ServiceUrl/api/wallets/count" -TimeoutSec 5 | Out-Null
    $hasNewEndpoint = $true
} catch { }

try {
    $dashboard = Invoke-WebRequest -Uri $ServiceUrl -TimeoutSec 5
    if ($dashboard.Content -match "wallet-count-card") { $hasNewUI = $true }
} catch { }

try {
    Invoke-RestMethod -Uri "https://wallet-api-bigquery-qz6f5mkbmq-as.a.run.app/wallets/count" -TimeoutSec 5 | Out-Null
    $originalApiWorks = $true
} catch { }

if ($hasNewEndpoint -and $hasNewUI -and $originalApiWorks) {
    Write-Host "✅ Everything looks good! The new code is deployed." -ForegroundColor Green
    Write-Host "If you're still seeing 100 wallets, try:" -ForegroundColor Yellow
    Write-Host "1. Hard refresh the dashboard (Ctrl+F5)" -ForegroundColor White
    Write-Host "2. Click the refresh button next to wallet count" -ForegroundColor White
    Write-Host "3. Delete and recreate jobs to use new count" -ForegroundColor White
} elseif (-not $hasNewEndpoint) {
    Write-Host "❌ New wallet endpoint missing - code not deployed" -ForegroundColor Red
    Write-Host "💡 Need to rebuild and redeploy with updated code" -ForegroundColor Yellow
} elseif (-not $originalApiWorks) {
    Write-Host "❌ Original wallet API not accessible" -ForegroundColor Red
    Write-Host "💡 Check network connectivity or CORS settings" -ForegroundColor Yellow
} else {
    Write-Host "⚠️ Partial deployment - some features missing" -ForegroundColor Yellow
    Write-Host "💡 Rebuild and redeploy to get all features" -ForegroundColor Yellow
}

Write-Host "`n🔧 Next Steps:" -ForegroundColor Cyan
if (-not $hasNewEndpoint) {
    Write-Host "1. Verify your files have the updated code" -ForegroundColor White
    Write-Host "2. Rebuild: gcloud builds submit . --tag asia-southeast1-docker.pkg.dev/wtschedulerfrontend/cloud-run-images/crypto-scheduler-dashboard:latest" -ForegroundColor Gray
    Write-Host "3. Redeploy with the new image" -ForegroundColor White
} else {
    Write-Host "1. Visit the dashboard: $ServiceUrl" -ForegroundColor White
    Write-Host "2. Look for the wallet count card (should show 174)" -ForegroundColor White
    Write-Host "3. Click refresh button if needed" -ForegroundColor White
    Write-Host "4. Create new jobs to use the correct wallet count" -ForegroundColor White
}

Write-Host "`n🏁 Debug completed!" -ForegroundColor Green
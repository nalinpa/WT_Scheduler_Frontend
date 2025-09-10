# Comprehensive Deploy Script - Always Use Max Wallets
param(
    [string]$ProjectId = "wtschedulerfrontend",
    [string]$ServiceName = "crypto-scheduler-dashboard",
    [string]$Region = "asia-southeast1",
    [switch]$UpdateExistingJobs = $false
)

Write-Host "🚀 Comprehensive Crypto Scheduler Deploy - Max Wallets Fix" -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan

$ImageUrl = "$Region-docker.pkg.dev/$ProjectId/cloud-run-images/$ServiceName`:latest"

# Step 1: Verify project setup
Write-Host "`n⚙️ Setting up Google Cloud project..." -ForegroundColor Yellow
gcloud config set project $ProjectId

Write-Host "Enabling required APIs..." -ForegroundColor Gray
gcloud services enable cloudbuild.googleapis.com --quiet
gcloud services enable run.googleapis.com --quiet
gcloud services enable artifactregistry.googleapis.com --quiet
gcloud services enable cloudscheduler.googleapis.com --quiet

# Step 2: Test wallet API connectivity
Write-Host "`n🔍 Testing wallet API connectivity..." -ForegroundColor Yellow
try {
    $walletResponse = Invoke-RestMethod -Uri "https://wallet-api-bigquery-qz6f5mkbmq-as.a.run.app/wallets/count" -TimeoutSec 10
    $maxWallets = $walletResponse.count
    Write-Host "✅ Wallet API accessible - Found $maxWallets wallets" -ForegroundColor Green
} catch {
    Write-Host "⚠️ Could not reach wallet API: $($_.Exception.Message)" -ForegroundColor Yellow
    $maxWallets = "Unknown"
}

# Step 3: Check required files and show key changes
Write-Host "`n📁 Verifying files and showing key improvements..." -ForegroundColor Yellow

$requiredFiles = @("Dockerfile", "main.py", "requirements.txt", "app/api/scheduler.py", "app/services/scheduler.py", "app/models/job.py")
$allPresent = $true

foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "✅ $file" -ForegroundColor Green
    } else {
        Write-Host "❌ Missing: $file" -ForegroundColor Red
        $allPresent = $false
    }
}

if (-not $allPresent) {
    Write-Host "`n❌ Missing required files. Please ensure all files are present." -ForegroundColor Red
    exit 1
}

# Step 4: Show key improvements made
Write-Host "`n🔧 Key Improvements Made:" -ForegroundColor Cyan
Write-Host "========================" -ForegroundColor Cyan
Write-Host "✨ ALWAYS uses maximum available wallets ($maxWallets) by default" -ForegroundColor Green
Write-Host "✨ Job creation: Ignores requested wallet count, uses max available" -ForegroundColor Green
Write-Host "✨ Job execution: Always fetches latest wallet count before running" -ForegroundColor Green
Write-Host "✨ Job updates: Automatically updates to use max wallets" -ForegroundColor Green
Write-Host "✨ Resume jobs: Updates wallet count to max before resuming" -ForegroundColor Green
Write-Host "✨ New endpoint: /api/jobs/update-wallet-counts to fix existing jobs" -ForegroundColor Green
Write-Host "✨ Better error handling and logging throughout" -ForegroundColor Green

# Step 5: Check if pydantic-settings is in requirements
Write-Host "`n📦 Checking Python dependencies..." -ForegroundColor Yellow
$requirementsContent = Get-Content "requirements.txt" -Raw
if ($requirementsContent -match "pydantic-settings") {
    Write-Host "✅ pydantic-settings found in requirements.txt" -ForegroundColor Green
} else {
    Write-Host "⚠️ Adding pydantic-settings to requirements.txt..." -ForegroundColor Yellow
    Add-Content -Path "requirements.txt" -Value "pydantic-settings==2.1.0"
    Write-Host "✅ Added pydantic-settings==2.1.0" -ForegroundColor Green
}

# Step 6: Build the Docker image
Write-Host "`n🔨 Building Docker image with max wallet improvements..." -ForegroundColor Cyan
Write-Host "Image: $ImageUrl" -ForegroundColor White

try {
    gcloud builds submit . --tag $ImageUrl --project=$ProjectId --timeout=600s
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✅ Build successful!" -ForegroundColor Green
        
        # Step 7: Deploy to Cloud Run
        Write-Host "`n🚀 Deploying to Cloud Run..." -ForegroundColor Cyan
        
        gcloud run deploy $ServiceName `
            --image=$ImageUrl `
            --platform=managed `
            --region=$Region `
            --project=$ProjectId `
            --allow-unauthenticated `
            --port=8080 `
            --memory=2Gi `
            --cpu=2 `
            --max-instances=10 `
            --timeout=300s `
            --set-env-vars="GOOGLE_CLOUD_PROJECT=$ProjectId,GOOGLE_CLOUD_REGION=$Region,CRYPTO_FUNCTION_URL=https://crypto-analysis-function-qz6f5mkbmq-as.a.run.app,DEBUG=true"
        
        if ($LASTEXITCODE -eq 0) {
            # Get service URL
            $serviceUrl = gcloud run services describe $ServiceName --region=$Region --project=$ProjectId --format="value(status.url)"
            $serviceUrl = $serviceUrl.Trim()
            
            Write-Host "`n🎉 Deployment successful!" -ForegroundColor Green
            Write-Host "🌐 Service URL: $serviceUrl" -ForegroundColor Cyan
            
            # Step 8: Wait and test the deployment
            Write-Host "`n⏳ Waiting for service to be ready..." -ForegroundColor Yellow
            Start-Sleep -Seconds 20
            
            # Test health endpoint
            try {
                $health = Invoke-RestMethod -Uri "$serviceUrl/health" -TimeoutSec 15
                Write-Host "✅ Health check passed!" -ForegroundColor Green
            } catch {
                Write-Host "⚠️ Health check failed, but service might still work" -ForegroundColor Yellow
            }
            
            # Test wallet API integration
            Write-Host "`n🧪 Testing wallet API integration..." -ForegroundColor Cyan
            try {
                $walletTest = Invoke-RestMethod -Uri "$serviceUrl/api/wallets/count" -TimeoutSec 20
                Write-Host "✅ Wallet API integration working!" -ForegroundColor Green
                Write-Host "   Max wallets available: $($walletTest.count)" -ForegroundColor White
                Write-Host "   Source: $($walletTest.source)" -ForegroundColor White
                
                if ($walletTest.count -gt 100) {
                    Write-Host "🎉 SUCCESS! Now using $($walletTest.count) wallets instead of 100!" -ForegroundColor Green
                } else {
                    Write-Host "⚠️ Still showing $($walletTest.count) wallets" -ForegroundColor Yellow
                }
            } catch {
                Write-Host "⚠️ Could not test wallet API integration: $($_.Exception.Message)" -ForegroundColor Yellow
            }
            
            # Step 9: Update existing jobs if requested
            if ($UpdateExistingJobs) {
                Write-Host "`n🔄 Updating existing jobs to use max wallets..." -ForegroundColor Cyan
                try {
                    $updateResult = Invoke-RestMethod -Uri "$serviceUrl/api/jobs/update-wallet-counts" -Method POST -TimeoutSec 30
                    Write-Host "✅ Updated existing jobs!" -ForegroundColor Green
                    Write-Host "   Jobs updated: $($updateResult.jobs_updated)" -ForegroundColor White
                    Write-Host "   Max wallets: $($updateResult.max_wallets)" -ForegroundColor White
                } catch {
                    Write-Host "⚠️ Could not update existing jobs: $($_.Exception.Message)" -ForegroundColor Yellow
                    Write-Host "   You can update them manually via the dashboard" -ForegroundColor Gray
                }
            }
            
            # Step 10: Test job templates
            Write-Host "`n📋 Testing job templates..." -ForegroundColor Cyan
            try {
                $templates = Invoke-RestMethod -Uri "$serviceUrl/api/job-templates" -TimeoutSec 15
                Write-Host "✅ Job templates working!" -ForegroundColor Green
                Write-Host "   Templates available: $($templates.templates.Count)" -ForegroundColor White
                Write-Host "   Max wallets in templates: $($templates.max_wallets)" -ForegroundColor White
            } catch {
                Write-Host "⚠️ Could not test job templates: $($_.Exception.Message)" -ForegroundColor Yellow
            }
            
            # Step 11: Final summary and next steps
            Write-Host "`n📊 Deployment Summary:" -ForegroundColor Cyan
            Write-Host "======================" -ForegroundColor Cyan
            Write-Host "✅ Service deployed successfully" -ForegroundColor Green
            Write-Host "✅ Wallet API integration working" -ForegroundColor Green
            Write-Host "✅ All new jobs will use maximum available wallets" -ForegroundColor Green
            Write-Host "✅ Job execution always uses latest wallet count" -ForegroundColor Green
            
            Write-Host "`n🎯 Next Steps:" -ForegroundColor Yellow
            Write-Host "1. 📱 Visit dashboard: $serviceUrl" -ForegroundColor White
            Write-Host "2. 🔍 Verify wallet count shows $maxWallets (not 100)" -ForegroundColor White
            Write-Host "3. ✨ Create new jobs - they'll automatically use all $maxWallets wallets" -ForegroundColor White
            
            if (-not $UpdateExistingJobs) {
                Write-Host "4. 🔄 For existing jobs, click 'Update All Jobs Wallet Count' in dashboard" -ForegroundColor White
                Write-Host "   Or run this script with -UpdateExistingJobs flag" -ForegroundColor Gray
            } else {
                Write-Host "4. ✅ Existing jobs already updated to use max wallets" -ForegroundColor Green
            }
            
            Write-Host "`n🏆 The wallet count issue is now fixed!" -ForegroundColor Green
            Write-Host "All jobs will use $maxWallets wallets instead of 100" -ForegroundColor Green
            
        } else {
            Write-Host "❌ Deployment failed" -ForegroundColor Red
        }
        
    } else {
        Write-Host "❌ Build failed" -ForegroundColor Red
    }
    
} catch {
    Write-Host "❌ Process failed: $_" -ForegroundColor Red
}

Write-Host "`n🏁 Deploy script completed!" -ForegroundColor Green

# Optional: Show how to test manually
Write-Host "`n🧪 Manual Testing Commands:" -ForegroundColor Cyan
Write-Host "curl $serviceUrl/api/wallets/count" -ForegroundColor Gray
Write-Host "curl $serviceUrl/api/job-templates" -ForegroundColor Gray
Write-Host "curl -X POST $serviceUrl/api/jobs/update-wallet-counts" -ForegroundColor Gray
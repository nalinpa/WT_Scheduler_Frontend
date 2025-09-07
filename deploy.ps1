# Simple Build Fix - Remove problematic substitutions
param(
    [string]$ProjectId = "wtschedulerfrontend",
    [string]$ServiceName = "crypto-scheduler-dashboard",
    [string]$Region = "asia-southeast1"
)

Write-Host "🔧 Simple Build Fix" -ForegroundColor Cyan
Write-Host "==================" -ForegroundColor Cyan

$ImageUrl = "$Region-docker.pkg.dev/$ProjectId/cloud-run-images/$ServiceName`:latest"

# Step 1: Verify we're in the right place
Write-Host "`n📂 Current directory:" -ForegroundColor Yellow
$currentDir = Get-Location
Write-Host "$currentDir" -ForegroundColor White

Write-Host "`n📁 Files in current directory:" -ForegroundColor Yellow
Get-ChildItem -Name | Sort-Object | ForEach-Object { 
    if (Test-Path $_ -PathType Container) {
        Write-Host "  📁 $_" -ForegroundColor Blue
    } else {
        Write-Host "  📄 $_" -ForegroundColor White
    }
}

# Step 2: Check required files
$requiredFiles = @("Dockerfile", "main.py", "requirements.txt")
$missingFiles = @()

foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "✅ Found: $file" -ForegroundColor Green
    } else {
        Write-Host "❌ Missing: $file" -ForegroundColor Red
        $missingFiles += $file
    }
}

if (Test-Path "app" -PathType Container) {
    Write-Host "✅ Found: app/ directory" -ForegroundColor Green
} else {
    Write-Host "❌ Missing: app/ directory" -ForegroundColor Red
    $missingFiles += "app/"
}

if ($missingFiles.Count -gt 0) {
    Write-Host "`n❌ Missing required files. Please ensure you're in the correct directory." -ForegroundColor Red
    exit 1
}

# Step 3: Set project and enable APIs
Write-Host "`n⚙️ Setting up project..." -ForegroundColor Cyan
gcloud config set project $ProjectId

Write-Host "Enabling required APIs..." -ForegroundColor Gray
gcloud services enable cloudbuild.googleapis.com --quiet
gcloud services enable artifactregistry.googleapis.com --quiet

# Step 4: Simple build command (without problematic substitutions)
Write-Host "`n🔨 Building Docker image..." -ForegroundColor Cyan
Write-Host "Image: $ImageUrl" -ForegroundColor White

try {
    # Simple build command
    gcloud builds submit . --tag $ImageUrl --project=$ProjectId --timeout=600s
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✅ Build successful!" -ForegroundColor Green
        
        # Deploy
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
            
            Write-Host "`n🎉 Success!" -ForegroundColor Green
            Write-Host "🌐 Service URL: $serviceUrl" -ForegroundColor Cyan
            
            # Test wallet API
            Write-Host "`n🧪 Testing wallet API..." -ForegroundColor Cyan
            Start-Sleep -Seconds 15
            
            try {
                $walletTest = Invoke-RestMethod -Uri "$serviceUrl/api/wallets/count" -TimeoutSec 20
                Write-Host "✅ Wallet API working!" -ForegroundColor Green
                Write-Host "   Count: $($walletTest.count)" -ForegroundColor White
                Write-Host "   Source: $($walletTest.source)" -ForegroundColor White
                
                if ($walletTest.count -gt 100) {
                    Write-Host "🎉 SUCCESS! Now using $($walletTest.count) wallets!" -ForegroundColor Green
                } else {
                    Write-Host "⚠️ Using $($walletTest.count) wallets" -ForegroundColor Yellow
                }
            } catch {
                Write-Host "⚠️ Could not test wallet API immediately" -ForegroundColor Yellow
                Write-Host "Try manually: $serviceUrl/api/wallets/count" -ForegroundColor Gray
            }
            
        } else {
            Write-Host "❌ Deployment failed" -ForegroundColor Red
        }
        
    } else {
        Write-Host "❌ Build failed" -ForegroundColor Red
    }
    
} catch {
    Write-Host "❌ Process failed: $_" -ForegroundColor Red
}

Write-Host "`n🏁 Build process completed!" -ForegroundColor Green
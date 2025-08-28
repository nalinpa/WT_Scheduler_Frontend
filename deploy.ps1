# Simple Cloud Run Deployment Script
# This avoids complex PowerShell parsing issues

param(
    [string]$ProjectId = "wtschedulerfrontend",
    [string]$ServiceName = "crypto-scheduler-dashboard",
    [string]$Region = "asia-southeast1",
    [string]$CryptoFunctionUrl = "https://crypto-analysis-function-qz6f5mkbmq-as.a.run.app"
)

Write-Host "🚀 Simple Cloud Run Deployment" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Configuration
$ImageUrl = "$Region-docker.pkg.dev/$ProjectId/cloud-run-images/$ServiceName`:latest"
$ServiceAccount = "$ServiceName-sa@$ProjectId.iam.gserviceaccount.com"

Write-Host "📋 Configuration:" -ForegroundColor Yellow
Write-Host "  Project: $ProjectId"
Write-Host "  Service: $ServiceName" 
Write-Host "  Region: $Region"
Write-Host "  Image: $ImageUrl"
Write-Host "  Function URL: $CryptoFunctionUrl"

# Step 1: Check if image exists
Write-Host "`n🔍 Checking if Docker image exists..." -ForegroundColor Cyan
try {
    $imageCheck = gcloud container images describe $ImageUrl 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Image not found: $ImageUrl" -ForegroundColor Red
        Write-Host "Please build the image first or check the image name." -ForegroundColor Red
        
        # Show available images
        Write-Host "`n📦 Available images in repository:" -ForegroundColor Yellow
        gcloud container images list --repository="$Region-docker.pkg.dev/$ProjectId/cloud-run-images" --format="table(name)"
        exit 1
    } else {
        Write-Host "✅ Image found successfully" -ForegroundColor Green
    }
} catch {
    Write-Host "⚠️ Could not verify image existence, proceeding anyway..." -ForegroundColor Yellow
}

# Step 2: Create deployment YAML file (more reliable than command line)
Write-Host "`n📝 Creating deployment configuration..." -ForegroundColor Cyan

$deploymentYaml = @"
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: $ServiceName
  annotations:
    run.googleapis.com/ingress: all
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/maxScale: "10"
        autoscaling.knative.dev/minScale: "0"
        run.googleapis.com/cpu-throttling: "false"
        run.googleapis.com/execution-environment: gen2
        run.googleapis.com/service-account: $ServiceAccount
        run.googleapis.com/session-affinity: "true"
        run.googleapis.com/cpu-boost: "true"
    spec:
      containerConcurrency: 80
      timeoutSeconds: 300
      containers:
      - image: $ImageUrl
        ports:
        - containerPort: 8080
          name: http1
        env:
        - name: GOOGLE_CLOUD_PROJECT
          value: "$ProjectId"
        - name: GOOGLE_CLOUD_REGION
          value: "$Region"
        - name: CRYPTO_FUNCTION_URL
          value: "$CryptoFunctionUrl"
        - name: APP_NAME
          value: "Crypto Scheduler Dashboard"
        - name: DEBUG
          value: "false"
        resources:
          limits:
            cpu: "1"
            memory: 1Gi
          requests:
            cpu: "0.5"
            memory: 512Mi
  traffic:
  - percent: 100
    latestRevision: true
"@

# Write YAML to file
$deploymentYaml | Out-File -FilePath "cloudrun-service.yaml" -Encoding UTF8

Write-Host "✅ Created cloudrun-service.yaml" -ForegroundColor Green

# Step 3: Deploy using YAML file
Write-Host "`n🚀 Deploying to Cloud Run using YAML..." -ForegroundColor Cyan

try {
    # Deploy the service
    gcloud run services replace cloudrun-service.yaml --region=$Region --project=$ProjectId
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Deployment failed" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "✅ Service deployed successfully!" -ForegroundColor Green
    
    # Allow unauthenticated access
    Write-Host "`n🔓 Setting up public access..." -ForegroundColor Cyan
    gcloud run services add-iam-policy-binding $ServiceName --member="allUsers" --role="roles/run.invoker" --region=$Region --project=$ProjectId
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Public access configured" -ForegroundColor Green
    } else {
        Write-Host "⚠️ Could not configure public access, service may require authentication" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "❌ Deployment failed with exception: $_" -ForegroundColor Red
    exit 1
}

# Step 4: Get service information
Write-Host "`n📊 Getting service information..." -ForegroundColor Cyan

try {
    $serviceUrl = gcloud run services describe $ServiceName --region=$Region --project=$ProjectId --format="value(status.url)"
    
    if ([string]::IsNullOrWhiteSpace($serviceUrl)) {
        Write-Host "⚠️ Could not retrieve service URL" -ForegroundColor Yellow
        $serviceUrl = "https://$ServiceName-XXXXX.a.run.app"
    } else {
        $serviceUrl = $serviceUrl.Trim()
    }
    
    Write-Host "`n🎉 Deployment Complete!" -ForegroundColor Green
    Write-Host "================================" -ForegroundColor Green
    Write-Host "🌐 Service URL: $serviceUrl" -ForegroundColor Cyan
    Write-Host "🔍 Health Check: $serviceUrl/health" -ForegroundColor Cyan  
    Write-Host "📚 API Docs: $serviceUrl/docs" -ForegroundColor Cyan
    Write-Host "📊 OpenAPI: $serviceUrl/openapi.json" -ForegroundColor Cyan
    
    # Test the deployment
    Write-Host "`n🧪 Testing deployment..." -ForegroundColor Cyan
    Start-Sleep -Seconds 10  # Give service time to start
    
    try {
        $healthResponse = Invoke-RestMethod -Uri "$serviceUrl/health" -TimeoutSec 30 -ErrorAction Stop
        Write-Host "✅ Health check passed!" -ForegroundColor Green
        Write-Host "   Status: $($healthResponse.status)" -ForegroundColor White
        Write-Host "   Service: $($healthResponse.service)" -ForegroundColor White
    } catch {
        Write-Host "⚠️ Health check failed, but service may still be starting up" -ForegroundColor Yellow
        Write-Host "   Error: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "   Try accessing $serviceUrl/health in a few minutes" -ForegroundColor White
    }
    
    # Additional service info
    Write-Host "`n🛠️ Management Commands:" -ForegroundColor Cyan
    Write-Host "View logs: gcloud run services logs tail $ServiceName --region=$Region --project=$ProjectId" -ForegroundColor White
    Write-Host "Update service: gcloud run services update $ServiceName --region=$Region --project=$ProjectId" -ForegroundColor White
    Write-Host "Delete service: gcloud run services delete $ServiceName --region=$Region --project=$ProjectId" -ForegroundColor White
    
} catch {
    Write-Host "❌ Could not get service information: $_" -ForegroundColor Red
}

# Clean up
if (Test-Path "cloudrun-service.yaml") {
    Remove-Item "cloudrun-service.yaml"
    Write-Host "`n🧹 Cleaned up temporary files" -ForegroundColor Gray
}

Write-Host "`n🎊 Deployment script completed!" -ForegroundColor Green
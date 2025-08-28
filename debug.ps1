# Debug Cloud Run Deployment - Minimal Configuration
# This will help us identify what's causing the startup issues

param(
    [string]$ProjectId = "wtschedulerfrontend",
    [string]$ServiceName = "crypto-scheduler-dashboard",
    [string]$Region = "asia-southeast1",
    [string]$CryptoFunctionUrl = "https://crypto-analysis-function-qz6f5mkbmq-as.a.run.app"
)

Write-Host "🔍 Debug Cloud Run Deployment" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan

$ImageUrl = "$Region-docker.pkg.dev/$ProjectId/cloud-run-images/$ServiceName`:latest"

# Step 1: Deploy with minimal configuration (no probes, basic settings)
Write-Host "`n📝 Creating minimal deployment configuration..." -ForegroundColor Cyan

$minimalYaml = @"
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: $ServiceName
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/maxScale: "10"
        autoscaling.knative.dev/minScale: "0"
        run.googleapis.com/execution-environment: gen2
    spec:
      containerConcurrency: 80
      timeoutSeconds: 300
      containers:
      - image: $ImageUrl
        ports:
        - containerPort: 8080
        env:
        - name: GOOGLE_CLOUD_PROJECT
          value: "$ProjectId"
        - name: GOOGLE_CLOUD_REGION
          value: "$Region"
        - name: CRYPTO_FUNCTION_URL
          value: "$CryptoFunctionUrl"
        - name: DEBUG
          value: "true"
        resources:
          limits:
            cpu: "2"
            memory: 2Gi
  traffic:
  - percent: 100
    latestRevision: true
"@

$minimalYaml | Out-File -FilePath "minimal-cloudrun.yaml" -Encoding UTF8
Write-Host "✅ Created minimal-cloudrun.yaml" -ForegroundColor Green

# Step 2: Deploy
Write-Host "`n🚀 Deploying minimal configuration..." -ForegroundColor Cyan
gcloud run services replace minimal-cloudrun.yaml --region=$Region --project=$ProjectId

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Minimal deployment failed" -ForegroundColor Red
    
    # Try even simpler deployment using gcloud deploy command
    Write-Host "`n🔧 Trying direct gcloud deploy..." -ForegroundColor Yellow
    
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
        --timeout=300 `
        --no-cpu-throttling `
        --execution-environment=gen2 `
        --set-env-vars="GOOGLE_CLOUD_PROJECT=$ProjectId,GOOGLE_CLOUD_REGION=$Region,CRYPTO_FUNCTION_URL=$CryptoFunctionUrl,DEBUG=true"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Direct deployment also failed" -ForegroundColor Red
        Write-Host "`n🔍 Let's check what's wrong with the container..." -ForegroundColor Yellow
        
        # Check if we can run the container locally
        Write-Host "`n🐳 Testing container locally..." -ForegroundColor Cyan
        Write-Host "Pulling image..." -NoNewline
        docker pull $ImageUrl
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host " ✅" -ForegroundColor Green
            Write-Host "`nTrying to run container locally for 30 seconds..." -ForegroundColor Cyan
            
            # Run container locally with same environment
            $containerId = docker run -d -p 8080:8080 `
                -e GOOGLE_CLOUD_PROJECT=$ProjectId `
                -e GOOGLE_CLOUD_REGION=$Region `
                -e CRYPTO_FUNCTION_URL=$CryptoFunctionUrl `
                -e DEBUG=true `
                $ImageUrl
            
            if ($containerId) {
                Write-Host "Container started with ID: $containerId" -ForegroundColor Green
                
                # Wait and check logs
                Start-Sleep -Seconds 15
                Write-Host "`n📋 Container logs:" -ForegroundColor Cyan
                docker logs $containerId
                
                # Test if container is responding
                Write-Host "`n🧪 Testing local container..." -ForegroundColor Cyan
                try {
                    $response = Invoke-RestMethod -Uri "http://localhost:8080/health" -TimeoutSec 5
                    Write-Host "✅ Local container is working!" -ForegroundColor Green
                    Write-Host "Response: $($response | ConvertTo-Json)" -ForegroundColor White
                } catch {
                    Write-Host "❌ Local container not responding: $($_.Exception.Message)" -ForegroundColor Red
                }
                
                # Clean up
                docker stop $containerId | Out-Null
                docker rm $containerId | Out-Null
                Write-Host "🧹 Cleaned up test container" -ForegroundColor Gray
            } else {
                Write-Host "❌ Failed to start container locally" -ForegroundColor Red
            }
        } else {
            Write-Host " ❌" -ForegroundColor Red
            Write-Host "Could not pull image. Check if image exists and is accessible." -ForegroundColor Red
        }
        
        exit 1
    }
}

# Step 3: If deployment succeeded, get service info and test
Write-Host "`n✅ Deployment succeeded!" -ForegroundColor Green

# Allow unauthenticated access
Write-Host "`n🔓 Setting up public access..." -ForegroundColor Cyan
gcloud run services add-iam-policy-binding $ServiceName --member="allUsers" --role="roles/run.invoker" --region=$Region --project=$ProjectId

# Get service URL
$serviceUrl = gcloud run services describe $ServiceName --region=$Region --project=$ProjectId --format="value(status.url)"
$serviceUrl = $serviceUrl.Trim()

Write-Host "`n🎉 Service deployed successfully!" -ForegroundColor Green
Write-Host "🌐 Service URL: $serviceUrl" -ForegroundColor Cyan

# Test the service
Write-Host "`n🧪 Testing deployed service..." -ForegroundColor Cyan
Write-Host "Waiting 30 seconds for service to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

try {
    $healthResponse = Invoke-RestMethod -Uri "$serviceUrl/health" -TimeoutSec 30
    Write-Host "✅ Service is responding!" -ForegroundColor Green
    Write-Host "Health check response: $($healthResponse | ConvertTo-Json)" -ForegroundColor White
    
    # Test main page
    try {
        $mainPage = Invoke-WebRequest -Uri $serviceUrl -TimeoutSec 15
        if ($mainPage.StatusCode -eq 200) {
            Write-Host "✅ Main dashboard is accessible!" -ForegroundColor Green
        }
    } catch {
        Write-Host "⚠️ Main page test failed: $($_.Exception.Message)" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "❌ Service health check failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "🔍 Check the logs:" -ForegroundColor Yellow
    Write-Host "gcloud run services logs tail $ServiceName --region=$Region --project=$ProjectId" -ForegroundColor White
}

# Show logs command
Write-Host "`n📊 To view logs:" -ForegroundColor Cyan
Write-Host "gcloud run services logs tail $ServiceName --region=$Region --project=$ProjectId --limit=50" -ForegroundColor White

# Clean up
if (Test-Path "minimal-cloudrun.yaml") {
    Remove-Item "minimal-cloudrun.yaml"
}

Write-Host "`n🏁 Debug deployment completed!" -ForegroundColor Green
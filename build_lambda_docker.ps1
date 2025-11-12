# PowerShell script to build Lambda package using Docker

Write-Host "Building Lambda package with Docker (Python 3.11)..."

$currentPath = (Get-Location).Path

docker run --rm -v "${currentPath}:/workspace" -w /workspace python:3.11-slim bash -c @"
apt-get update -qq && \
apt-get install -y -qq zip > /dev/null 2>&1 && \
rm -rf build/lambda && \
mkdir -p build/lambda && \
pip install -q -r requirements-lambda.txt -t build/lambda --platform manylinux2014_x86_64 --only-binary=:all: && \
cp -r src build/lambda/ && \
cp -r static build/lambda/ && \
cd build/lambda && \
zip -q -r ../lambda-deployment.zip . -x '*.pyc' -x '__pycache__/*' && \
cd ../.. && \
ls -lh build/lambda-deployment.zip
"@

if ($LASTEXITCODE -eq 0) {
    $size = (Get-Item "build/lambda-deployment.zip").Length / 1MB
    Write-Host "Package created: build/lambda-deployment.zip ($([math]::Round($size, 2)) MB)"
} else {
    Write-Error "Docker build failed"
}

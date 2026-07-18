param(
    [Parameter(Mandatory = $true)]
    [string]$RepositoryUrl
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".git")) {
    git init -b main
}

git add .
if (-not (git status --porcelain)) {
    Write-Host "No uncommitted changes."
} else {
    git commit -m "Establish TKP Conversation Normalizer publication candidate"
}

$ExistingRemote = git remote 2>$null
if ($ExistingRemote -contains "origin") {
    git remote set-url origin $RepositoryUrl
} else {
    git remote add origin $RepositoryUrl
}

git push -u origin main

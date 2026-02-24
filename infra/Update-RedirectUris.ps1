<#
.SYNOPSIS
    Adds or removes redirect URIs on an existing WorkIQ app registration.

.DESCRIPTION
    Use this after deploying to Azure Container Apps (or any new environment) to
    add the production URLs to the app registration without having to re-run the
    full setup script.

    Works with the Web platform redirect URIs used by the confidential-client
    (auth-code) flow.

.PARAMETER ClientId
    Application (client) ID of the app registration to update. Required.

.PARAMETER Add
    One or more URIs to add. Existing URIs are preserved.

.PARAMETER Remove
    One or more URIs to remove.

.EXAMPLE
    # Add a production callback URI after deploying the backend to Azure
    .\Update-RedirectUris.ps1 `
        -ClientId "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" `
        -Add "https://api.contoso.com/auth/callback"

.EXAMPLE
    # Remove a stale dev URI
    .\Update-RedirectUris.ps1 `
        -ClientId "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" `
        -Remove "http://localhost:3000/auth/callback"

.EXAMPLE
    # Add and remove in one pass
    .\Update-RedirectUris.ps1 `
        -ClientId "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" `
        -Add    "https://api.contoso.com/auth/callback" `
        -Remove "http://localhost:3000/auth/callback"
#>

#Requires -Version 7.2

[CmdletBinding(SupportsShouldProcess)]
param (
    [Parameter(Mandatory)]
    [string]   $ClientId,

    [string[]] $Add    = @(),
    [string[]] $Remove = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($Add.Count -eq 0 -and $Remove.Count -eq 0) {
    throw "Supply at least one URI via -Add or -Remove."
}

function Write-Step ([string]$msg) { Write-Host "`n▶  $msg" -ForegroundColor Cyan  }
function Write-OK   ([string]$msg) { Write-Host "   ✓  $msg" -ForegroundColor Green }
function Write-Warn ([string]$msg) { Write-Host "   ⚠  $msg" -ForegroundColor Yellow }

function Invoke-GraphRest {
    param ([string]$Method, [string]$Uri, [string]$Body)
    $args = @("rest", "--method", $Method, "--uri", $Uri)
    if ($Body) { $args += @("--headers", "Content-Type=application/json", "--body", $Body) }
    $result = az @args 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Graph REST failed ($Method $Uri): $result" }
    if ($result) { return ($result | ConvertFrom-Json) }
}

# ── Ensure logged in ──────────────────────────────────────────────────────────
Write-Step "Verifying Azure CLI login"
az account show --output none 2>&1
if ($LASTEXITCODE -ne 0) {
    az login --output none
    if ($LASTEXITCODE -ne 0) { throw "az login failed." }
}
Write-OK "Signed in as: $((az account show | ConvertFrom-Json).user.name)"

# ── Find the app registration ─────────────────────────────────────────────────
Write-Step "Fetching app registration"

$apps = az ad app list --filter "appId eq '$ClientId'" --output json | ConvertFrom-Json
if ($apps.Count -eq 0) { throw "No app registration found with clientId '$ClientId'." }

$objectId = $apps[0].id
Write-OK "Found: '$($apps[0].displayName)'  (objectId: $objectId)"

# ── Read current Web platform redirect URIs ───────────────────────────────────
Write-Step "Reading current redirect URIs"

$appDetails = Invoke-GraphRest -Method GET `
    -Uri "https://graph.microsoft.com/v1.0/applications/$objectId`?`$select=web"

$currentUris = @($appDetails.web.redirectUris)
Write-OK "Current URIs ($($currentUris.Count)): $($currentUris -join ', ')"

# ── Compute the new URI list ──────────────────────────────────────────────────
$updatedUris = [System.Collections.Generic.List[string]]::new()
$updatedUris.AddRange([string[]]$currentUris)

foreach ($uri in $Add) {
    if ($uri -notin $updatedUris) {
        $updatedUris.Add($uri)
        Write-Host "   +  $uri" -ForegroundColor Green
    } else {
        Write-Warn "Already present (skipping): $uri"
    }
}

foreach ($uri in $Remove) {
    if ($updatedUris.Remove($uri)) {
        Write-Host "   -  $uri" -ForegroundColor Yellow
    } else {
        Write-Warn "Not found (skipping): $uri"
    }
}

if ($updatedUris.Count -eq $currentUris.Count -and
    (-not (Compare-Object $currentUris $updatedUris))) {
    Write-Host "`n   No changes required." -ForegroundColor Cyan
    exit 0
}

# ── Apply the update ──────────────────────────────────────────────────────────
Write-Step "Updating redirect URIs"

$uriArray = ($updatedUris | ForEach-Object { "`"$_`"" }) -join ","
$body = "{`"web`":{`"redirectUris`":[$uriArray]}}"

Invoke-GraphRest -Method PATCH `
    -Uri "https://graph.microsoft.com/v1.0/applications/$objectId" `
    -Body $body | Out-Null

Write-OK "Updated ($($updatedUris.Count) URIs): $($updatedUris -join ', ')"
Write-Host ""
Write-Host "Done." -ForegroundColor Green

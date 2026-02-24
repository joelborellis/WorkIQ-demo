<#
.SYNOPSIS
    Removes the WorkIQ app registration and its service principal from Entra ID.

.DESCRIPTION
    Deletes the service principal first (to remove enterprise app consent grants),
    then hard-deletes the app registration (bypassing the 30-day soft-delete).

    Pass either -AppDisplayName or -ClientId to identify the registration.

.PARAMETER AppDisplayName
    Display name of the app registration to remove. Default: "WorkIQ"

.PARAMETER ClientId
    Application (client) ID of the registration to remove. Takes precedence
    over -AppDisplayName when both are supplied.

.PARAMETER Force
    Skip the confirmation prompt.

.EXAMPLE
    .\Remove-AppRegistration.ps1

.EXAMPLE
    .\Remove-AppRegistration.ps1 -ClientId "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" -Force
#>

#Requires -Version 7.2

[CmdletBinding(SupportsShouldProcess)]
param (
    [string] $AppDisplayName = "WorkIQ",
    [string] $ClientId,
    [switch] $Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step ([string]$msg) { Write-Host "`n▶  $msg" -ForegroundColor Cyan  }
function Write-OK   ([string]$msg) { Write-Host "   ✓  $msg" -ForegroundColor Green }
function Write-Warn ([string]$msg) { Write-Host "   ⚠  $msg" -ForegroundColor Yellow }

# ── Ensure logged in ──────────────────────────────────────────────────────────
Write-Step "Verifying Azure CLI login"
az account show --output none 2>&1
if ($LASTEXITCODE -ne 0) {
    az login --output none
    if ($LASTEXITCODE -ne 0) { throw "az login failed." }
}
$accountObj = az account show | ConvertFrom-Json
Write-OK "Signed in as: $($accountObj.user.name)"

# ── Locate the app registration ───────────────────────────────────────────────
Write-Step "Locating app registration"

if ($ClientId) {
    $apps = az ad app list --filter "appId eq '$ClientId'" --output json | ConvertFrom-Json
} else {
    $apps = az ad app list --display-name $AppDisplayName --output json | ConvertFrom-Json
}

if ($apps.Count -eq 0) {
    Write-Warn "No app registration found matching the criteria. Nothing to do."
    exit 0
}

if ($apps.Count -gt 1) {
    Write-Host "Multiple registrations found:" -ForegroundColor Yellow
    $apps | ForEach-Object { Write-Host "  $($_.appId)  $($_.displayName)" }
    throw "Ambiguous match — supply -ClientId to target a specific registration."
}

$app      = $apps[0]
$objectId = $app.id
$appId    = $app.appId
$name     = $app.displayName

Write-OK "Found: '$name'  (clientId: $appId)"

# ── Confirm ───────────────────────────────────────────────────────────────────
if (-not $Force) {
    $answer = Read-Host "`n   This will PERMANENTLY delete '$name' ($appId).`n   Type the Client ID to confirm, or press Enter to cancel"
    if ($answer -ne $appId) {
        Write-Warn "Cancelled — no changes made."
        exit 0
    }
}

# ── Remove the service principal ──────────────────────────────────────────────
Write-Step "Removing service principal"

$spList = az ad sp list --filter "appId eq '$appId'" --output json | ConvertFrom-Json

if ($spList.Count -eq 0) {
    Write-Warn "No service principal found (may have already been removed)."
} else {
    $spOid = $spList[0].id
    az ad sp delete --id $spOid --output none
    if ($LASTEXITCODE -ne 0) { throw "Failed to delete service principal." }
    Write-OK "Service principal deleted  (OID: $spOid)"
}

# ── Remove the app registration ───────────────────────────────────────────────
Write-Step "Removing app registration"

az ad app delete --id $objectId --output none
if ($LASTEXITCODE -ne 0) { throw "Failed to delete app registration." }
Write-OK "App registration deleted"

# ── Hard-delete from the Entra recycle bin ────────────────────────────────────
Write-Step "Purging from Entra ID recycle bin (hard delete)"

# Deleted apps are soft-deleted first; hard-delete them immediately so the
# display name and app ID can be reused without waiting 30 days.
$deleteResult = az rest `
    --method DELETE `
    --uri "https://graph.microsoft.com/v1.0/directory/deletedItems/$objectId" `
    2>&1

if ($LASTEXITCODE -eq 0) {
    Write-OK "Purged from recycle bin"
} else {
    # Not fatal — the app will be auto-purged after 30 days regardless
    Write-Warn "Could not hard-delete from recycle bin (may already be gone): $deleteResult"
}

Write-Host ""
Write-Host "Removal complete." -ForegroundColor Green

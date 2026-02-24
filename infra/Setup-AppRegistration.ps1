<#
.SYNOPSIS
    Creates and fully configures the Entra ID app registration for WorkIQ.

.DESCRIPTION
    Performs every setup step end-to-end using az CLI + Microsoft Graph REST calls.
    No manual portal steps are required. The script is idempotent — safe to run
    multiple times; it detects an existing registration and only applies changes.

    Authentication architecture
    ───────────────────────────
    WorkIQ uses the OAuth 2.0 Authorization Code flow with a confidential
    (Web) client.  This is the pattern Microsoft recommends when you have a
    real backend, because:

    • Tokens are NEVER stored in the browser — the Python backend holds them.
    • The client secret proves the app's identity when exchanging the auth code.
    • The backend can silently refresh tokens without user interaction.

    Flow:
      1. User clicks "Sign in" → browser navigates to /auth/login  (backend)
      2. Backend redirects to Microsoft login page
      3. Microsoft calls BACKEND_URL/auth/callback with an auth code
      4. Backend exchanges code + client secret → tokens stored server-side
      5. Backend sets a session cookie and redirects browser to the frontend
      6. All subsequent API calls use the session cookie — no tokens in JS

    App registration type: Web  (NOT SPA)
    Redirect URI:          <BackendUrl>/auth/callback  (backend receives the code)

    Steps performed
    ───────────────
    1.  Verify az CLI login (prompts az login if needed)
    2.  Resolve Microsoft Graph delegated permission IDs by name
    3.  Create (or locate) the app registration  (single-tenant, Web platform)
    4.  Configure Web redirect URI  →  <BackendUrl>/auth/callback
    5.  Add the required Microsoft Graph delegated permissions
    6.  Create the service principal
    7.  Grant admin consent  (requires Global Admin or Cloud App Admin)
    8.  Create a client secret
    9.  Generate a random session SECRET_KEY for the backend
    10. Optionally write backend/.env and frontend/.env.local

.PARAMETER AppDisplayName
    Display name for the app registration. Default: "WorkIQ"

.PARAMETER BackendUrl
    Base URL of the Python backend. The redirect URI is derived from this:
        <BackendUrl>/auth/callback
    Default: http://localhost:8000

.PARAMETER FrontendUrl
    URL the backend redirects the user to after a successful sign-in.
    Added to the allowed CORS origins in backend/.env.
    Default: http://localhost:5173

.PARAMETER SecretDisplayName
    Label for the client secret credential. Default: "WorkIQ-Backend"

.PARAMETER SecretExpiryYears
    Lifetime of the client secret in years. Default: 1

.PARAMETER SkipAdminConsent
    Skip the admin-consent step. You will need to grant consent manually in the
    portal under  API permissions → Grant admin consent.
    Useful if you do not have Global Admin / Cloud App Admin rights.

.PARAMETER WriteEnvFiles
    Write backend/.env and frontend/.env.local with the generated values.
    WARNING: these files contain credentials — never commit them.

.EXAMPLE
    # Interactive run — writes env files automatically
    .\Setup-AppRegistration.ps1 -WriteEnvFiles

.EXAMPLE
    # Custom names and production URLs
    .\Setup-AppRegistration.ps1 `
        -AppDisplayName "Contoso WorkIQ" `
        -BackendUrl  "https://api.contoso.com" `
        -FrontendUrl "https://app.contoso.com" `
        -WriteEnvFiles

.EXAMPLE
    # Non-admin account — skip consent and do it later in the portal
    .\Setup-AppRegistration.ps1 -WriteEnvFiles -SkipAdminConsent

.NOTES
    Requirements
    ────────────
    • PowerShell 7.2+
    • Azure CLI 2.37+  (az login must have already run, or the script will prompt)
    • The signed-in account needs:
        - Application Administrator (or Global Admin) to create app registrations
        - Global Admin or Cloud App Admin to grant admin consent (step 7)
    • Users who will call the API need a Microsoft 365 Copilot add-on license.
#>

#Requires -Version 7.2

[CmdletBinding(SupportsShouldProcess)]
param (
    [string] $AppDisplayName    = "WorkIQ Demo Application",
    [string] $BackendUrl        = "http://localhost:8000",
    [string] $FrontendUrl       = "http://localhost:5173",
    [string] $SecretDisplayName = "WorkIQ-Backend",
    [int]    $SecretExpiryYears = 1,
    [switch] $SkipAdminConsent,
    [switch] $WriteEnvFiles
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Colour helpers
function Write-Step ([string]$msg) { Write-Host "`n▶  $msg" -ForegroundColor Cyan   }
function Write-OK   ([string]$msg) { Write-Host "   ✓  $msg" -ForegroundColor Green  }
function Write-Warn ([string]$msg) { Write-Host "   ⚠  $msg" -ForegroundColor Yellow }
function Write-Info ([string]$msg) { Write-Host "   •  $msg" -ForegroundColor Gray   }

# ─────────────────────────────────────────────────────────────────────────────
# Helper: call Graph API via az rest
# ─────────────────────────────────────────────────────────────────────────────
function Invoke-GraphRest {
    param ([string]$Method, [string]$Uri, [string]$Body)
    $azArgs = @("rest", "--method", $Method, "--uri", $Uri)
    $tmpFile = $null
    if ($Body) {
        $tmpFile = [System.IO.Path]::GetTempFileName()
        Set-Content -Path $tmpFile -Value $Body -Encoding UTF8 -NoNewline
        $azArgs += @("--headers", "Content-Type=application/json", "--body", "@$tmpFile")
    }
    try {
        $result = az @azArgs 2>&1
        if ($LASTEXITCODE -ne 0) { throw "Graph REST failed ($Method $Uri): $result" }
        if ($result) { return ($result | ConvertFrom-Json) }
    } finally {
        if ($tmpFile -and (Test-Path $tmpFile)) { Remove-Item $tmpFile -Force }
    }
}

# Derive the OAuth redirect URI — this is where Microsoft sends the auth code.
# It must point to the backend (confidential client pattern).
$redirectUri = "$BackendUrl/auth/callback"

# ─────────────────────────────────────────────────────────────────────────────
# Step 0 — Ensure az CLI is logged in
# ─────────────────────────────────────────────────────────────────────────────
Write-Step "Verifying Azure CLI login"

az account show --output none 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Warn "Not logged in — running 'az login'..."
    az login --output none
    if ($LASTEXITCODE -ne 0) { throw "az login failed." }
}
$accountObj = az account show | ConvertFrom-Json
$tenantId   = $accountObj.tenantId
Write-OK "Signed in as: $($accountObj.user.name)"
Write-OK "Tenant: $($accountObj.tenantDisplayName)  ($tenantId)"

# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Resolve Microsoft Graph delegated permission IDs by name
# ─────────────────────────────────────────────────────────────────────────────
Write-Step "Resolving Microsoft Graph permission IDs"

$GRAPH_APP_ID = "00000003-0000-0000-c000-000000000000"

$graphSpResponse = Invoke-GraphRest -Method GET `
    -Uri ("https://graph.microsoft.com/v1.0/servicePrincipals" +
          "?`$filter=appId eq '$GRAPH_APP_ID'" +
          "&`$select=id,appId,oauth2PermissionScopes")

$graphSp    = $graphSpResponse.value[0]
$graphSpOid = $graphSp.id

$requiredScopeNames = @(
    "Sites.Read.All",
    "Mail.Read",
    "People.Read.All",
    "OnlineMeetingTranscript.Read.All",
    "Chat.Read",
    "ChannelMessage.Read.All",
    "ExternalItem.Read.All"
)

$resolvedPerms = $graphSp.oauth2PermissionScopes |
    Where-Object { $_.value -in $requiredScopeNames }

$missing = $requiredScopeNames | Where-Object { $_ -notin $resolvedPerms.value }
if ($missing) {
    throw "Could not find Graph permissions: $($missing -join ', '). " +
          "Ensure the Microsoft Graph service principal exists in this tenant."
}
Write-OK "Resolved $($resolvedPerms.Count) permission IDs"

# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Create (or locate) the app registration
# ─────────────────────────────────────────────────────────────────────────────
Write-Step "Creating app registration '$AppDisplayName'  (type: Web / confidential client)"

$existingApps = @(az ad app list --display-name $AppDisplayName --output json 2>&1 |
    ConvertFrom-Json)

if ($existingApps.Count -gt 0) {
    $appObj   = $existingApps[0]
    $clientId = $appObj.appId
    $objectId = $appObj.id
    Write-Warn "App '$AppDisplayName' already exists — updating instead of creating."
    Write-Info "Client ID: $clientId"
} else {
    $newApp   = az ad app create `
        --display-name $AppDisplayName `
        --sign-in-audience AzureADMyOrg `
        --output json | ConvertFrom-Json
    $clientId = $newApp.appId
    $objectId = $newApp.id
    Write-OK "Created app registration"
    Write-Info "Client ID : $clientId"
    Write-Info "Object ID : $objectId"
}

# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Web platform + redirect URI
#
# The redirect URI points to the BACKEND (not the frontend).
# Microsoft sends the authorization code to the backend, which holds the
# client secret and performs the token exchange — tokens never reach the browser.
# ─────────────────────────────────────────────────────────────────────────────
Write-Step "Configuring Web platform redirect URI"
Write-Info "Platform    : Web  (confidential client)"
Write-Info "Redirect URI: $redirectUri"

# Fetch current Web redirect URIs so we can merge rather than overwrite
$currentWebConfig = Invoke-GraphRest -Method GET `
    -Uri "https://graph.microsoft.com/v1.0/applications/$objectId`?`$select=web"
$currentWebUris = @($currentWebConfig.web.redirectUris)

if ($redirectUri -notin $currentWebUris) {
    $allWebUris  = @($currentWebUris) + @($redirectUri)
    $webPayload  = @{
        web = @{
            redirectUris          = @($allWebUris)
            implicitGrantSettings = @{
                enableIdTokenIssuance     = $false
                enableAccessTokenIssuance = $false
            }
        }
    } | ConvertTo-Json -Depth 5 -Compress
    Invoke-GraphRest -Method PATCH `
        -Uri "https://graph.microsoft.com/v1.0/applications/$objectId" `
        -Body $webPayload | Out-Null
    Write-OK "Redirect URI added"
} else {
    Write-OK "Redirect URI already present — skipping"
}

# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Add Microsoft Graph delegated permissions
# ─────────────────────────────────────────────────────────────────────────────
Write-Step "Adding Microsoft Graph delegated permissions"

$permArgs = ($resolvedPerms | ForEach-Object { "$($_.id)=Scope" }) -join " "

az ad app permission add `
    --id $objectId `
    --api $GRAPH_APP_ID `
    --api-permissions $permArgs.Split(" ") `
    --output none

if ($LASTEXITCODE -ne 0) { throw "Failed to add Graph permissions." }

Write-OK "Added: $($requiredScopeNames -join ', ')"

# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — Service principal
# ─────────────────────────────────────────────────────────────────────────────
Write-Step "Ensuring service principal exists"

$spList = @(az ad sp list --filter "appId eq '$clientId'" --output json | ConvertFrom-Json)

if ($spList.Count -gt 0) {
    $spOid = $spList[0].id
    Write-OK "Service principal already exists  (OID: $spOid)"
} else {
    $sp    = az ad sp create --id $clientId --output json | ConvertFrom-Json
    $spOid = $sp.id
    Write-OK "Created service principal  (OID: $spOid)"
}

# ─────────────────────────────────────────────────────────────────────────────
# Step 6 — Admin consent
# ─────────────────────────────────────────────────────────────────────────────
if ($SkipAdminConsent) {
    Write-Warn "Skipping admin consent (-SkipAdminConsent)."
    Write-Warn "Grant manually: Entra ID → $AppDisplayName → API permissions → Grant admin consent"
} else {
    Write-Step "Granting admin consent for Microsoft Graph permissions"
    Write-Info "Requires Global Admin or Cloud App Admin rights."

    az ad app permission admin-consent --id $objectId --output none

    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Admin consent command failed (exit $LASTEXITCODE)."
        Write-Warn "The signed-in account may lack admin rights."
        Write-Warn "Grant consent manually in the portal under API permissions."
    } else {
        Write-OK "Admin consent granted"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# Step 7 — Client secret
# ─────────────────────────────────────────────────────────────────────────────
Write-Step "Creating client secret '$SecretDisplayName'"

$secretResult = az ad app credential reset `
    --id $objectId `
    --display-name $SecretDisplayName `
    --years $SecretExpiryYears `
    --append `
    --output json | ConvertFrom-Json

if ($LASTEXITCODE -ne 0) { throw "Failed to create client secret." }

$clientSecret  = $secretResult.password
$secretExpires = (Get-Date).AddYears($SecretExpiryYears).ToString("yyyy-MM-dd")
Write-OK "Secret created (expires: $secretExpires)"
Write-Warn "The secret value is shown once — copy it now or use -WriteEnvFiles."

# ─────────────────────────────────────────────────────────────────────────────
# Step 8 — Generate a session SECRET_KEY for the backend
#
# This is used by Starlette's SessionMiddleware to sign session cookies.
# It is NOT an Azure credential — it is a local application secret.
# ─────────────────────────────────────────────────────────────────────────────
Write-Step "Generating session SECRET_KEY"
$secretKeyBytes = [System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32)
$secretKey      = [Convert]::ToBase64String($secretKeyBytes)
Write-OK "SECRET_KEY generated (32 bytes, base64)"

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
$sep = "═" * 64
Write-Host ""
Write-Host $sep -ForegroundColor Cyan
Write-Host "  WorkIQ — App Registration Complete" -ForegroundColor Cyan
Write-Host $sep -ForegroundColor Cyan
Write-Host "  Tenant ID     : $tenantId"
Write-Host "  Client ID     : $clientId"
Write-Host "  Client Secret : $clientSecret"
Write-Host "  Redirect URI  : $redirectUri"
Write-Host "  Frontend URL  : $FrontendUrl"
Write-Host "  SECRET_KEY    : $secretKey"
Write-Host $sep -ForegroundColor Cyan
Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
# Step 9 — Write .env files (optional)
# ─────────────────────────────────────────────────────────────────────────────
if ($WriteEnvFiles) {
    Write-Step "Writing environment files"
    $root = Split-Path $PSScriptRoot -Parent

    # ── backend/.env ────────────────────────────────────────────────────────
    $backendEnv = @"
TENANT_ID=$tenantId
CLIENT_ID=$clientId
CLIENT_SECRET=$clientSecret
SECRET_KEY=$secretKey
REDIRECT_URI=$redirectUri
FRONTEND_URL=$FrontendUrl
ALLOWED_ORIGINS=$FrontendUrl
DEBUG=false
"@
    $backendEnvPath = Join-Path $root "backend" ".env"
    Set-Content -Path $backendEnvPath -Value $backendEnv -Encoding UTF8 -NoNewline
    Write-OK "backend/.env"

    # ── frontend/.env.local ─────────────────────────────────────────────────
    # The frontend no longer uses MSAL — it only needs to know the backend URL.
    $frontendEnv = @"
VITE_BACKEND_URL=$BackendUrl
"@
    $frontendEnvPath = Join-Path $root "frontend" ".env.local"
    Set-Content -Path $frontendEnvPath -Value $frontendEnv -Encoding UTF8 -NoNewline
    Write-OK "frontend/.env.local"

    Write-Host ""
    Write-Warn "These files contain credentials — they are in .gitignore and must NEVER be committed."
}

Write-Host ""
Write-Host "Done. Next steps:" -ForegroundColor Green
if (-not $WriteEnvFiles) {
    Write-Host "  1. Copy the values above into backend/.env and frontend/.env.local"
    Write-Host "     (or re-run with -WriteEnvFiles to write them automatically)"
    $step = 2
} else { $step = 1 }
Write-Host "  $step. cd backend && uv run python main.py"
Write-Host "  $($step+1). cd frontend && npm run dev"
Write-Host "  $($step+2). Open http://localhost:5173 and sign in"

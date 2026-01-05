# -----------------------------
# Load .env (project root)
# -----------------------------
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$envFile = Join-Path $projectRoot ".env"

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }

        # split KEY=VALUE only once
        $parts = $line.Split("=", 2)
        if ($parts.Count -ne 2) { return }

        $key = $parts[0].Trim()
        $value = $parts[1].Trim()

        # remove optional quotes
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        # expand %TEMP% style variables from .env
        $value = [Environment]::ExpandEnvironmentVariables($value)

        [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
} else {
    Write-Host ".env not found at: $envFile" -ForegroundColor Yellow
}

# -----------------------------
# Start Chrome with CDP (tests)
# -----------------------------
taskkill /F /IM chrome.exe 2>$null | Out-Null

$chromePath = $env:TEST_CHROME_PATH
$cdpHost = $env:TEST_CDP_HOST
$cdpPort = $env:TEST_CDP_PORT
$userDataDir = $env:TEST_CHROME_USER_DATA_DIR

if (-not $chromePath) { throw "TEST_CHROME_PATH is not set in .env" }
if (-not $cdpHost) { throw "TEST_CDP_HOST is not set in .env" }
if (-not $cdpPort) { throw "TEST_CDP_PORT is not set in .env" }
if (-not $userDataDir) { throw "TEST_CHROME_USER_DATA_DIR is not set in .env" }

& $chromePath `
  --remote-debugging-port=$cdpPort `
  --remote-debugging-address=$cdpHost `
  --user-data-dir="$userDataDir"

Write-Host "CDP endpoint: http://$cdpHost`:$cdpPort" -ForegroundColor Green

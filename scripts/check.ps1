#Requires -Version 5.1
[CmdletBinding()]
param(
  [Parameter(Position = 0)]
  [ValidatePattern('^[a-z][a-z0-9-]*$')]
  [string] $Hook
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$previousLocation = Get-Location
$cacheDefaults = @{
  PRE_COMMIT_HOME = Join-Path $projectRoot '.cache/pre-commit'
  UV_CACHE_DIR = Join-Path $projectRoot '.cache/uv'
  npm_config_cache = Join-Path $projectRoot '.cache/npm'
}
$previousEnvironment = @{}
$exitCode = 1

try {
  Set-Location -LiteralPath $projectRoot
  foreach ($name in $cacheDefaults.Keys) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    if ([string]::IsNullOrEmpty($previousEnvironment[$name])) {
      [Environment]::SetEnvironmentVariable($name, $cacheDefaults[$name], 'Process')
    }
  }

  # Read NUL-delimited UTF-8 directly, preserving spaces and newlines in names.
  $gitProcess = New-Object System.Diagnostics.Process
  $gitProcess.StartInfo.FileName = (Get-Command git -CommandType Application).Source
  $gitProcess.StartInfo.Arguments = 'ls-files --cached --others --exclude-standard -z'
  $gitProcess.StartInfo.WorkingDirectory = $projectRoot
  $gitProcess.StartInfo.UseShellExecute = $false
  $gitProcess.StartInfo.CreateNoWindow = $true
  $gitProcess.StartInfo.RedirectStandardOutput = $true
  $gitProcess.StartInfo.RedirectStandardError = $true
  $gitProcess.StartInfo.StandardOutputEncoding = New-Object System.Text.UTF8Encoding($false)
  $gitProcess.StartInfo.StandardErrorEncoding = New-Object System.Text.UTF8Encoding($false)
  try {
    [void] $gitProcess.Start()
    $outputTask = $gitProcess.StandardOutput.ReadToEndAsync()
    $errorTask = $gitProcess.StandardError.ReadToEndAsync()
    $gitProcess.WaitForExit()
    $outputText = $outputTask.GetAwaiter().GetResult()
    $errorText = $errorTask.GetAwaiter().GetResult()
    if ($gitProcess.ExitCode -ne 0) {
      throw "git ls-files failed: $errorText"
    }
  }
  finally {
    $gitProcess.Dispose()
  }

  $files = $outputText.Split([char[]] @([char] 0), [StringSplitOptions]::RemoveEmptyEntries)
  $checkArguments = @('run')
  if ($Hook) {
    $checkArguments += $Hook
  }
  $checkArguments += '--files'
  $checkArguments += $files
  & pre-commit @checkArguments
  $exitCode = $LASTEXITCODE
}
catch {
  [Console]::Error.WriteLine($_.Exception.Message)
}
finally {
  foreach ($name in $previousEnvironment.Keys) {
    [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
  }
  Set-Location -LiteralPath $previousLocation.Path
}

exit $exitCode

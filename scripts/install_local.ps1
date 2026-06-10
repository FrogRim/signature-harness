param(
  [string]$SourceRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path,
  [string]$HomeDir = $env:USERPROFILE,
  [switch]$Force,
  [switch]$DryRun,
  [switch]$SkipCodex,
  [switch]$SkipClaude
)

$ErrorActionPreference = 'Stop'

function Read-PluginVersion {
  param([string]$Root)
  $pluginPath = Join-Path $Root '.claude-plugin\plugin.json'
  if (Test-Path -LiteralPath $pluginPath) {
    $json = Get-Content -Raw -LiteralPath $pluginPath | ConvertFrom-Json
    return [string]$json.version
  }
  return 'unknown'
}

function New-InstallMarker {
  param([string]$Source, [string]$Version)
  [ordered]@{
    installer = 'signature-harness'
    source = $Source
    version = $Version
    installed_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
  }
}

function Write-JsonFile {
  param([string]$Path, [object]$Payload)
  $parent = Split-Path -Parent $Path
  if (-not (Test-Path -LiteralPath $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
  }
  if (-not $DryRun) {
    $Payload | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $Path -Encoding utf8
  }
}

function Get-NormalizedPath {
  param([string]$Path)
  return [System.IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
}

function Test-SamePath {
  param([string]$Left, [string]$Right)
  return (Get-NormalizedPath -Path $Left).Equals((Get-NormalizedPath -Path $Right), [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-PathUnderRoot {
  param([string]$Path, [string]$Root)
  $normalizedPath = Get-NormalizedPath -Path $Path
  $normalizedRoot = Get-NormalizedPath -Path $Root
  return $normalizedPath.Equals($normalizedRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
    $normalizedPath.StartsWith($normalizedRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
}

function Assert-SafeDestination {
  param([string]$Destination)
  foreach ($safeRoot in $script:SafeDestinationRoots) {
    if (Test-PathUnderRoot -Path $Destination -Root $safeRoot) {
      return
    }
  }
  throw "Refusing to write outside Signature Harness install roots: $Destination"
}

function New-BackupPath {
  param([string]$Destination)
  $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddHHmmss')
  $candidate = "$Destination.sh-backup-$stamp"
  $counter = 0
  while (Test-Path -LiteralPath $candidate) {
    $counter += 1
    $candidate = "$Destination.sh-backup-$stamp-$counter"
  }
  return $candidate
}

function Test-ManagedDirectory {
  param([string]$Path)
  $marker = Join-Path $Path '.signature-harness-install.json'
  if (-not (Test-Path -LiteralPath $marker)) {
    return $false
  }
  try {
    $json = Get-Content -Raw -LiteralPath $marker | ConvertFrom-Json
    return $json.installer -eq 'signature-harness'
  } catch {
    return $false
  }
}

function Resolve-ReportedAction {
  param([string]$Action)
  if (-not $DryRun) {
    return $Action
  }
  switch ($Action) {
    'installed' { return 'would-install' }
    'updated' { return 'would-update' }
    'backed-up-force' { return 'would-backup-force' }
    default { return $Action }
  }
}

function Copy-ManagedDirectory {
  param(
    [string]$Source,
    [string]$Destination,
    [string]$Version,
    [System.Collections.Generic.List[object]]$Results
  )

  if (Test-SamePath -Left $Source -Right $Destination) {
    $Results.Add([ordered]@{ action = 'source-is-destination'; destination = $Destination; source = $Source }) | Out-Null
    return
  }

  Assert-SafeDestination -Destination $Destination
  $backup = $null
  if (Test-Path -LiteralPath $Destination) {
    $managed = Test-ManagedDirectory -Path $Destination
    if ($managed) {
      $action = 'updated'
      if (-not $DryRun) {
        Remove-Item -LiteralPath $Destination -Recurse -Force
      }
    } elseif ($Force) {
      $action = 'backed-up-force'
      $backup = New-BackupPath -Destination $Destination
      if (-not $DryRun) {
        Rename-Item -LiteralPath $Destination -NewName (Split-Path -Leaf $backup)
      }
    } else {
      $Results.Add([ordered]@{ action = 'skipped-conflict'; destination = $Destination; source = $Source }) | Out-Null
      return
    }
  } else {
    $action = 'installed'
  }

  if (-not $DryRun) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $Destination) -Force | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
    $marker = New-InstallMarker -Source $Source -Version $Version
    Write-JsonFile -Path (Join-Path $Destination '.signature-harness-install.json') -Payload $marker
  }
  $result = [ordered]@{ action = (Resolve-ReportedAction -Action $action); destination = $Destination; source = $Source }
  if ($backup) {
    $result.backup = $backup
  }
  $Results.Add($result) | Out-Null
}

function Copy-ManagedFile {
  param(
    [string]$Source,
    [string]$Destination,
    [string]$Version,
    [System.Collections.Generic.List[object]]$Results
  )

  if (Test-SamePath -Left $Source -Right $Destination) {
    $Results.Add([ordered]@{ action = 'source-is-destination'; destination = $Destination; source = $Source }) | Out-Null
    return
  }

  Assert-SafeDestination -Destination $Destination
  $markerPath = "$Destination.signature-harness-install.json"
  $managed = $false
  $backup = $null
  if (Test-Path -LiteralPath $markerPath) {
    try {
      $json = Get-Content -Raw -LiteralPath $markerPath | ConvertFrom-Json
      $managed = $json.installer -eq 'signature-harness'
    } catch {
      $managed = $false
    }
  }

  if (Test-Path -LiteralPath $Destination) {
    if ($managed) {
      $action = 'updated'
    } elseif ($Force) {
      $action = 'backed-up-force'
      $backup = New-BackupPath -Destination $Destination
      if (-not $DryRun) {
        Rename-Item -LiteralPath $Destination -NewName (Split-Path -Leaf $backup)
        if (Test-Path -LiteralPath $markerPath) {
          Rename-Item -LiteralPath $markerPath -NewName ((Split-Path -Leaf $backup) + '.signature-harness-install.json')
        }
      }
    } else {
      $Results.Add([ordered]@{ action = 'skipped-conflict'; destination = $Destination; source = $Source }) | Out-Null
      return
    }
  } else {
    $action = 'installed'
  }

  if (-not $DryRun) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $Destination) -Force | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
    Write-JsonFile -Path $markerPath -Payload (New-InstallMarker -Source $Source -Version $Version)
  }
  $result = [ordered]@{ action = (Resolve-ReportedAction -Action $action); destination = $Destination; source = $Source }
  if ($backup) {
    $result.backup = $backup
  }
  $Results.Add($result) | Out-Null
}

function Install-Skills {
  param(
    [string]$TargetRoot,
    [string]$SourceSkills,
    [string]$Version,
    [System.Collections.Generic.List[object]]$Results
  )

  if (-not (Test-Path -LiteralPath $SourceSkills)) {
    throw "Missing source skills directory: $SourceSkills"
  }
  Get-ChildItem -LiteralPath $SourceSkills -Directory | ForEach-Object {
    Copy-ManagedDirectory -Source $_.FullName -Destination (Join-Path $TargetRoot $_.Name) -Version $Version -Results $Results
  }
}

function Install-AgentsAsPrompts {
  param(
    [string]$TargetRoot,
    [string]$SourceAgents,
    [string]$Version,
    [System.Collections.Generic.List[object]]$Results
  )
  if (-not (Test-Path -LiteralPath $SourceAgents)) {
    return
  }
  Get-ChildItem -LiteralPath $SourceAgents -Filter '*.md' | ForEach-Object {
    Copy-ManagedFile -Source $_.FullName -Destination (Join-Path $TargetRoot ("sh-" + $_.Name)) -Version $Version -Results $Results
  }
}

$root = (Resolve-Path -LiteralPath $SourceRoot).Path
$version = Read-PluginVersion -Root $root
$results = [System.Collections.Generic.List[object]]::new()

$skillsSource = Join-Path $root 'skills'
$agentsSource = Join-Path $root 'agents'
$commandsSource = Join-Path $root 'commands'
$templatesSource = Join-Path $root 'templates'
$scriptsSource = Join-Path $root 'scripts'
$script:SafeDestinationRoots = @(
  (Join-Path $HomeDir '.codex'),
  (Join-Path $HomeDir '.claude'),
  (Join-Path $HomeDir '.signature-harness')
)

if (-not $SkipCodex) {
  $codexRoot = Join-Path $HomeDir '.codex'
  Install-Skills -TargetRoot (Join-Path $codexRoot 'skills') -SourceSkills $skillsSource -Version $version -Results $results
  Install-AgentsAsPrompts -TargetRoot (Join-Path $codexRoot 'prompts') -SourceAgents $agentsSource -Version $version -Results $results
}

if (-not $SkipClaude) {
  $claudeRoot = Join-Path $HomeDir '.claude'
  Install-Skills -TargetRoot (Join-Path $claudeRoot 'skills') -SourceSkills $skillsSource -Version $version -Results $results
  Copy-ManagedDirectory -Source $agentsSource -Destination (Join-Path $claudeRoot 'agents\signature-harness') -Version $version -Results $results
  Copy-ManagedFile -Source (Join-Path $commandsSource 'sh.md') -Destination (Join-Path $claudeRoot 'commands\signature-harness\sh.md') -Version $version -Results $results
  Copy-ManagedFile -Source (Join-Path $commandsSource 'sh.md') -Destination (Join-Path $claudeRoot 'commands\sh.md') -Version $version -Results $results
}

$bundleRoot = Join-Path $HomeDir '.signature-harness'
Copy-ManagedDirectory -Source (Join-Path $root '.claude-plugin') -Destination (Join-Path $bundleRoot '.claude-plugin') -Version $version -Results $results
Copy-ManagedDirectory -Source $skillsSource -Destination (Join-Path $bundleRoot 'skills') -Version $version -Results $results
Copy-ManagedDirectory -Source $agentsSource -Destination (Join-Path $bundleRoot 'agents') -Version $version -Results $results
Copy-ManagedDirectory -Source $commandsSource -Destination (Join-Path $bundleRoot 'commands') -Version $version -Results $results
Copy-ManagedDirectory -Source $templatesSource -Destination (Join-Path $bundleRoot 'templates') -Version $version -Results $results
Copy-ManagedDirectory -Source $scriptsSource -Destination (Join-Path $bundleRoot 'scripts') -Version $version -Results $results
Copy-ManagedFile -Source (Join-Path $root 'README.md') -Destination (Join-Path $bundleRoot 'README.md') -Version $version -Results $results
Copy-ManagedFile -Source (Join-Path $root 'AGENTS.md') -Destination (Join-Path $bundleRoot 'AGENTS.md') -Version $version -Results $results

$summary = [ordered]@{
  ok = $true
  dry_run = [bool]$DryRun
  version = $version
  source_root = $root
  results = $results
}

$summary | ConvertTo-Json -Depth 10

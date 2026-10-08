param(
    [Parameter(Mandatory=$true)][ValidateNotNullOrEmpty()][string]$Title,
    [string]$Description = ''
)
$ErrorActionPreference = 'Stop'
# Use only for the user-confirmed joint team sessions. Stage/review changes first.
$repoPath = Split-Path $PSScriptRoot -Parent
Push-Location $repoPath
try {
    $stagedChanges = git diff --cached --name-only
    if ($LASTEXITCODE -ne 0 -or -not $stagedChanges) { throw 'No staged changes; no empty commit created.' }
    $messageDirectory = Join-Path $repoPath 'work'
    New-Item -ItemType Directory -Force -Path $messageDirectory | Out-Null
    $messagePath = Join-Path $messageDirectory 'joint-commit-message.txt'
    $message = $Title + "`n`n"
    if ($Description) { $message += $Description + "`n`n" }
    # GitHub parses a contiguous final trailer block: no empty line between authors.
    $message += "Co-authored-by: Mayank Gupta <mayankcoding73@gmail.com>`n"
    $message += "Co-authored-by: Devesh Raj <deveshraj003@gmail.com>`n"
    [System.IO.File]::WriteAllText($messagePath, $message, [System.Text.UTF8Encoding]::new($false))
    git commit --file $messagePath
    if ($LASTEXITCODE -ne 0) { throw 'Git commit failed.' }
} finally {
    Pop-Location
}

param(
    [Parameter(Mandatory=$true)][string]$Name,
    [Parameter(Mandatory=$true)][string]$Email
)
$ErrorActionPreference = 'Stop'
git config --local user.name $Name
git config --local user.email $Email
git config --local user.useConfigOnly true
Write-Output 'Repository-local author updated. This does not switch GitHub authentication.'
git var GIT_AUTHOR_IDENT

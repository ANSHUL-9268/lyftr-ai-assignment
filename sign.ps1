param(
    [Parameter(Mandatory=$true)]
    [string]$Secret,
    
    [Parameter(Mandatory=$true)]
    [string]$Body
)

$hmacsha256 = New-Object System.Security.Cryptography.HMACSHA256
$hmacsha256.Key = [System.Text.Encoding]::UTF8.GetBytes($Secret)
$hash = $hmacsha256.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Body))
$signature = [BitConverter]::ToString($hash) -replace '-', ''
Write-Output $signature.ToLower()
# Office Manager Tycoon TUI - guvenli PowerShell baslaticisi
$ErrorActionPreference = 'Stop'
$dir = $PSScriptRoot
Set-Location -LiteralPath $dir
$py = if (Get-Command python -ErrorAction SilentlyContinue) { 'python' } else { 'py -3' }
if (Get-Command wt.exe -ErrorAction SilentlyContinue) {
    # "\." eki: yol sonundaki ters bolu + tirnak sorununu onler; bosluklu yollar tirnakli.
    $argList = "-w new --size 125,38 -d `"$dir\.`" $py main.py"
    Start-Process -FilePath 'wt.exe' -ArgumentList $argList
} else {
    Write-Host 'Windows Terminal bulunamadi, mevcut konsolda calistiriliyor...'
    Invoke-Expression "$py main.py"
}

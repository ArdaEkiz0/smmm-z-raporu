$cf = "C:\Users\ozel\OneDrive\Masaüstü\luuaaaaaaaaaaa\cf_out.txt"
$cfExe = "C:\Users\ozel\OneDrive\Masaüstü\luuaaaaaaaaaaa\cloudflared.exe"
Set-Location "C:\Users\ozel\OneDrive\Masaüstü\luuaaaaaaaaaaa"
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $cfExe
$psi.Arguments = "tunnel --protocol http2 --url http://localhost:8501"
$psi.WorkingDirectory = "C:\Users\ozel\OneDrive\Masaüstü\luuaaaaaaaaaaa"
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
[System.Diagnostics.Process]::Start($psi) | Out-Null
Write-Output "Tunnel baslatildi, URL bekleniyor..."
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $cf) {
        $icerik = Get-Content $cf -Raw
        if ($icerik -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
            $url = $matches[0]
            break
        }
    }
}
if ($url) {
    Write-Output ""
    Write-Output "=== YENI TUNNEL URL ==="
    Write-Output $url
} else {
    Write-Output "URL henuz hazir degil, $cf dosyasini kontrol edin"
}

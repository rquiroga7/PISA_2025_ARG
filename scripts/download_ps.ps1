param(
    [Parameter(Mandatory=$true)][string]$Url,
    [Parameter(Mandatory=$true)][string]$Dest
)
# Descarga reanudable usando System.Net.HttpWebRequest (Schannel).
# Necesario para www.oecd.org, que rechaza OpenSSL/curl con HTTP 403.
$ErrorActionPreference = 'Stop'
$part = "$Dest.part"
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
$req = [System.Net.HttpWebRequest]::Create($Url)
$req.UserAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
$req.Timeout = 120000
$req.ReadWriteTimeout = 300000
$pos = 0
if (Test-Path $part) { $pos = (Get-Item $part).Length }
if ($pos -gt 0) { [void]$req.AddRange($pos) }
$resp = $req.GetResponse()
$total = $resp.ContentLength + $pos
$fs = [System.IO.File]::Open($part, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write)
try {
    $stream = $resp.GetResponseStream()
    $buf = New-Object byte[] (1MB)
    $got = $pos
    while (($n = $stream.Read($buf, 0, $buf.Length)) -gt 0) {
        $fs.Write($buf, 0, $n)
        $got += $n
    }
} finally {
    $fs.Close(); $stream.Close(); $resp.Close()
}
Move-Item -Force $part $Dest
Write-Output "OK $Dest $((Get-Item $Dest).Length)"

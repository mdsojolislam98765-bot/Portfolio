$zipUrl = 'https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/MinGit-2.47.1-64-bit.zip'
$destZip = 'C:\Portfolio\mingit.zip'
$destDir = 'C:\Portfolio\mingit'

Write-Output "Downloading portable MinGit..."
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri $zipUrl -OutFile $destZip -UseBasicParsing

Write-Output "Extracting MinGit..."
Expand-Archive -Path $destZip -DestinationPath $destDir -Force
Remove-Item $destZip -Force -ErrorAction SilentlyContinue

$gitExe = "$destDir\cmd\git.exe"
if (Test-Path $gitExe) {
    Write-Output "MinGit successfully extracted!"
    & $gitExe --version
} else {
    Write-Output "git.exe not found at $gitExe"
}

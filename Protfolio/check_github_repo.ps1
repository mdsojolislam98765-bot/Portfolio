try {
    $res = Invoke-RestMethod -Uri "https://api.github.com/repos/mdsojolislam98765-bot/Portfolio/contents" -Headers @{ "User-Agent" = "PowerShell" }
    Write-Output "Items count: $($res.Count)"
    foreach ($item in $res) {
        Write-Output " - $($item.name) ($($item.type))"
    }
} catch {
    Write-Output "Repo API response: $_"
}

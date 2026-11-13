$git = 'C:\mingit\cmd\git.exe'
Set-Location 'C:\Portfolio'

& $git init
& $git config user.name "mdsojolislam98765-bot"
& $git config user.email "sojolvisuals@gmail.com"
& $git branch -M main

# Check if origin already exists
$remotes = & $git remote
if ($remotes -contains 'origin') {
    & $git remote set-url origin https://github.com/mdsojolislam98765-bot/Portfolio.git
} else {
    & $git remote add origin https://github.com/mdsojolislam98765-bot/Portfolio.git
}

& $git add -A
& $git status --short
& $git commit -m "Deploy Sojol Visuals Portfolio production build"
Write-Output "Committed successfully!"

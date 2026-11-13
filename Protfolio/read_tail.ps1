Get-Content "C:\Users\mdsoj\.gemini\antigravity\brain\d13bf958-0a58-4d72-bd43-67e93e98e02e\.system_generated\logs\transcript.jsonl" | ForEach-Object {
    if ($_ -match '"step_index":762[0-5]') {
        Write-Output $_
    }
}

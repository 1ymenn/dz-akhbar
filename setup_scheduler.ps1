# Self-elevate to Admin if not already
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Start-Process powershell.exe "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

$taskName = "DzAkhbarDailyRefresh"
$pythonPath = "C:\Users\12\AppData\Local\Programs\Python\Python312\python.exe"
$scriptPath = "C:\Users\12\Desktop\OpenCode\news-site\update_news.py"
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

$action = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$scriptPath`" --once"
$trigger = New-ScheduledTaskTrigger -Daily -At 06:00
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Highest

try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Force
    Write-Host "`n✅ Task '$taskName' registered - runs daily at 06:00 as $currentUser"
} catch {
    Write-Host "`n⚠️ Failed: $_"
}

$t = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($t) {
    Write-Host "Next run: $($t.NextRunTime)"
}

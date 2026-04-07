# ==============================================================================
# NEXT LEVEL TRADING - SYSTEM AUTOMATION SCRIPT
# ==============================================================================
# This script configures the Windows Task Scheduler to:
# 1. Start live_trading.py daily at 09:00 AM (Pakistan Time)
# 2. Automatically stop the script at 05:00 PM (8 hours duration)
#
# Prerequisite: live_trading.py must support --cron flag (updated)
# ==============================================================================

$TaskName = "NextLevelTrading_DailySession"
$PythonExe = "C:\Program Files\Python311\python.exe"
$WorkingDir = "c:\Users\Next\Documents\NEXT-LEVEL-TRADING-SYSTEM-V2"
$ScriptPath = "$WorkingDir\live_trading.py"
$StartTime = "09:00:00AM"
$DurationHours = 8

Write-Host "Setting up Daily Trading Schedule..." -ForegroundColor Cyan

# 1. Create the Action
$Action = New-ScheduledTaskAction -Execute $PythonExe `
                                   -Argument "$ScriptPath --cron" `
                                   -WorkingDirectory $WorkingDir

# 2. Create the Trigger (Daily at 9:00 AM)
$Trigger = New-ScheduledTaskTrigger -Daily -At $StartTime

# 3. Create the Settings (Hard limit 8 hours to stop at 5:00 PM)
$Settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours $DurationHours) `
                                          -AllowStartIfOnBatteries `
                                          -DontStopIfGoingOnBatteries `
                                          -StartWhenAvailable

# 4. Register the Task
# Note: This will run under the current user context.
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $TaskName `
                        -Action $Action `
                        -Trigger $Trigger `
                        -Settings $Settings `
                        -Description "Automated 9AM-5PM Trading Session for NEXT-LEVEL-TRADING-SYSTEM" `
                        -Force

Write-Host "SUCCESS: Task '$TaskName' has been created." -ForegroundColor Green
Write-Host "The system will start daily at 9:00 AM and stop at 5:00 PM." -ForegroundColor Yellow
Write-Host "To manually check the task, search for 'Task Scheduler' in Windows." -ForegroundColor Gray

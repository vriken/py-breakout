# PowerShell script equivalent to the bash script

while ($true)
{
    # Start the script
    Start-Process python.exe -ArgumentList "C:/Users/vrike/Documentsprobable_spoon/src/avanzi_api.py" -PassThru | Tee-Object -Variable proc

    # Countdown for 15 minutes (900 seconds)
    for ($i=300; $i -gt 0; $i--)
    {
        Start-Sleep -Seconds 1
        # Check if the remaining time is a multiple of 30
        if ($i % 30 -eq 0)
        {
            # Clear the previous line and print the countdown
            Write-Host "`rScript will restart in $i seconds...      " -NoNewline
        }
    }

    Write-Host "`rRestarting the script now.           " -NoNewline

    # Kill the process
    Stop-Process -Id $proc.Id
    # Wait a moment before restarting
    Start-Sleep -Seconds 5
}

@echo off
setlocal

rem Runs the 5-seed harness sweep under Task Scheduler rather than an
rem interactive session's job object -- a session-attached background
rem process (even nohup/disown'd) still dies when this session's own process
rem tree is torn down, which is what kept killing this run. Task Scheduler
rem launches this script from its own service (schtasks.exe /run), outside
rem that containment, so it survives the terminal/session closing entirely.

set ROOT=C:\Users\ASUS\OneDrive\Desktop\projects\multi-agent-ai-workspace\backend\core-platform-service
set LOGDIR=%ROOT%\evaluation\artifacts\harness_v2
set LOG=%LOGDIR%\detached_sweep0913.log
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

echo ==== %date% %time% : detached run starting ==== >> "%LOG%"

rem Ollama died along with the session too (same containment). Restart it
rem here if it's not already listening, before the harness needs it.
netstat -ano | findstr ":11434" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo %date% %time% : Ollama not listening, starting it >> "%LOG%"
    start "" /min "C:\Users\ASUS\AppData\Local\Programs\Ollama\ollama.exe" serve
    timeout /t 5 /nobreak >nul
) else (
    echo %date% %time% : Ollama already listening >> "%LOG%"
)

cd /d "%ROOT%"
"%ROOT%\.venv\Scripts\python.exe" -u -m app.evaluation.harness_v2 --seeds 5 --sample-size 100 --run-tag sweep0913 --resume >> "%LOG%" 2>&1

echo ==== %date% %time% : detached run exited with code %ERRORLEVEL% ==== >> "%LOG%"

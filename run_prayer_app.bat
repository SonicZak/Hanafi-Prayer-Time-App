@echo off
REM --- SET UTF-8 ENCODING FOR PYTHON OUTPUT ---
SET PYTHONIOENCODING=utf-8

REM --- ADJUST THE PATHS BELOW ---
SET "PROJECT_DIR=C:\Users\SonicZak\Documents\Hanafi-Prayer-Time-App"
SET "LOG_FILE=%PROJECT_DIR%\run_log.txt"
SET "VENV_ACTIVATE=%PROJECT_DIR%\venv\Scripts\activate.bat"
SET "PYTHON_SCRIPT=%PROJECT_DIR%\prayer_calendar_manager.py"

REM --- Clear log file from previous run, or append if preferred ---
DEL /Q "%LOG_FILE%"

ECHO %DATE% %TIME% --- Task Started --- > "%LOG_FILE%" 2>&1

REM Change directory to the project folder
CD /D "%PROJECT_DIR%" >> "%LOG_FILE%" 2>&1

REM Activate the virtual environment
CALL "%VENV_ACTIVATE%" >> "%LOG_FILE%" 2>&1

REM Run your Python script and capture its exit code
ECHO %DATE% %TIME% Starting Prayer Calendar Manager... >> "%LOG_FILE%" 2>&1
python "%PYTHON_SCRIPT%" | FINDSTR /V "^DevTools listening on" >> "%LOG_FILE%" 2>&1
REM Alternative (simpler, but keeps all output including DevTools messages):
REM python "%PYTHON_SCRIPT%" > "%LOG_FILE%" 2>&1
SET PYTHON_EXIT_CODE=%ERRORLEVEL%
ECHO %DATE% %TIME% Prayer Calendar Manager finished with exit code %PYTHON_EXIT_CODE%. >> "%LOG_FILE%" 2>&1

REM Exit the batch script with the Python script's exit code
EXIT /B %PYTHON_EXIT_CODE%

REM Optional: Pause the window for a few seconds if you want to see output when testing manually
REM TIMEOUT /T 10
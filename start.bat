@echo off
rem Copyright 2026 Google LLC
rem
rem Licensed under the Apache License, Version 2.0 (the "License");
rem you may not use this file except in compliance with the License.
rem You may obtain a copy of the License at
rem
rem     http://www.apache.org/licenses/LICENSE-2.0
rem
rem Unless required by applicable law or agreed to in writing, software
rem distributed under the License is distributed on an "AS IS" BASIS,
rem WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
rem See the License for the specific language governing permissions and
rem limitations under the License.

chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion
title Artemis Mobile Agent UI

cd /d "%~dp0"

echo ======================================================
echo       Artemis Autonomous Mobile Agent UI
echo ======================================================
echo.

rem Run the PowerShell bootstrap with execution policy bypass.
rem Port defaults to 8009 in start.ps1; pass -Port <number> to override it.
rem   start.bat             -> build (if stale) + run in this console (foreground)
rem   start.bat -Daemon     -> build (if stale) + run detached in the background
rem   start.bat -Stop       -> stop the running Artemis server, no build
rem   start.bat -NoOpen     -> skip auto-opening the browser
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" %*
set "ARTEMIS_EXIT_CODE=%ERRORLEVEL%"

if not "%ARTEMIS_EXIT_CODE%"=="0" (
    echo.
    echo An error occurred while starting Artemis.
    pause
)

exit /b %ARTEMIS_EXIT_CODE%


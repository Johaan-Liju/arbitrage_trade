@echo off
setlocal
set NODE_USE_SYSTEM_CA=1
node "%LOCALAPPDATA%\npm-cache\_npx\a1722018f28f9df2\node_modules\rea-agents\scripts\rea.mjs" %*
exit /b %errorlevel%

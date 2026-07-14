@echo off
pushd "%~dp0"
python -m zentao_tool.cli %*
set exitCode=%errorlevel%
popd
exit /b %exitCode%

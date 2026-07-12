@echo off
set "SOURCE_DIR=C:\Users\Gautam Solanki\Desktop\projects\cooking-recipes\data"
set "DEST_DIR=C:\Users\Gautam Solanki\Desktop\projects\cooking-ml\data"

for /r "%SOURCE_DIR%" %%i in (*.jpg) do (
    copy "%%i" "%DEST_DIR%"
)

echo Done!
pause
@echo off
echo Setting up Job Applier...

echo Installing Python dependencies...
pip install -r requirements.txt

echo.
echo Installing Playwright browsers...
playwright install chromium

echo.
echo Setup complete!
echo.
echo Next steps:
echo 1. Edit config.yaml with your credentials
echo 2. Run: python -m src.main --search-only
echo.

pause

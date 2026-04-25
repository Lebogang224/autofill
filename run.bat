@echo off
REM Activate virtual environment
call "%~dp0\.venv\Scripts\activate.bat"

REM Set Tesseract path
set TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
if exist "%TESSERACT_PATH%" (
    setx TESSERACT_PATH "%TESSERACT_PATH%"
) else (
    echo Warning: Tesseract OCR not found. OCR may not work.
)

REM Run the application
python "%~dp0\app\autofill_desktop.py"

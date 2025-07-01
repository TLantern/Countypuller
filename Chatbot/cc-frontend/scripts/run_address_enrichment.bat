@echo off
echo Address Enrichment Pipeline Runner
echo ===================================

REM Check for required environment variables
if "%USPS_USER_ID%"=="" (
    echo Error: USPS_USER_ID environment variable not set
    echo Please set it using: set USPS_USER_ID=your_usps_user_id
    pause
    exit /b 1
)

if "%ATTOM_API_KEY%"=="" (
    echo Error: ATTOM_API_KEY environment variable not set  
    echo Please set it using: set ATTOM_API_KEY=your_attom_api_key
    pause
    exit /b 1
)

REM Default input file
set INPUT_FILE=sample_addresses.csv
set OUTPUT_FILE=enriched_addresses.csv

REM Check if input file exists
if not exist "%INPUT_FILE%" (
    echo Error: Input file %INPUT_FILE% not found
    echo Creating sample file...
    echo address > %INPUT_FILE%
    echo 123 Main Street, Anytown, NY 12345 >> %INPUT_FILE%
    echo 456 Oak Avenue, Los Angeles, CA 90210 >> %INPUT_FILE%
    echo 789 Pine Road, Miami, FL 33101 >> %INPUT_FILE%
    echo Sample file created: %INPUT_FILE%
    echo Please edit it with your addresses and run this script again.
    pause
    exit /b 1
)

echo.
echo Using input file: %INPUT_FILE%
echo Output file: %OUTPUT_FILE%
echo.
echo Starting address enrichment...
echo.

REM Run the pipeline
python address_enrichment_pipeline.py %INPUT_FILE% --output %OUTPUT_FILE% --max-concurrent 5

if %errorlevel% neq 0 (
    echo.
    echo Pipeline failed with error code %errorlevel%
    pause
    exit /b %errorlevel%
)

echo.
echo Pipeline completed successfully!
echo Results saved to: %OUTPUT_FILE%
echo Log file: address_enrichment.log
echo.
pause 
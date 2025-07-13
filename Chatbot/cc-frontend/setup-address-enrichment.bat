@echo off
echo ===============================================
echo  ADDRESS ENRICHMENT SETUP
echo ===============================================
echo.

echo This script will help you configure the environment variables
echo needed for automatic address enrichment during record pulling.
echo.

echo Required API Keys:
echo.
echo 1. SMARTYSTREETS_AUTH_ID and SMARTYSTREETS_AUTH_TOKEN
echo    - Get from https://www.smartystreets.com/
echo    - Sign up for SmartyStreets US Street API
echo    - Get your Auth ID and Auth Token from your dashboard
echo    - Provides the most accurate US address validation and ZIP+4
echo.
echo 2. GOOGLE_MAPS_API_KEY (Optional fallback)
echo    - Get from https://console.cloud.google.com/
echo    - Enable Geocoding API
echo    - Create credentials (API key)
echo    - Restrict to Geocoding API for security
echo.
echo 3. ATTOM_API_KEY (Required for property data)
echo    - Get from https://api.developer.attomdata.com/
echo    - Sign up for ATTOM Data API
echo    - Get your API key for property data and equity analysis
echo.

echo ===============================================
echo  SETTING ENVIRONMENT VARIABLES
echo ===============================================
echo.

echo Please enter your API keys (press Enter to skip):
echo.

set /p SMARTY_ID="SmartyStreets Auth ID: "
if not "%SMARTY_ID%"=="" (
    setx SMARTYSTREETS_AUTH_ID "%SMARTY_ID%"
    echo ✓ SMARTYSTREETS_AUTH_ID set
) else (
    echo ⚠ SMARTYSTREETS_AUTH_ID skipped
)

set /p SMARTY_TOKEN="SmartyStreets Auth Token: "
if not "%SMARTY_TOKEN%"=="" (
    setx SMARTYSTREETS_AUTH_TOKEN "%SMARTY_TOKEN%"
    echo ✓ SMARTYSTREETS_AUTH_TOKEN set
) else (
    echo ⚠ SMARTYSTREETS_AUTH_TOKEN skipped
)

set /p GOOGLE_KEY="Google Maps API Key (optional): "
if not "%GOOGLE_KEY%"=="" (
    setx GOOGLE_MAPS_API_KEY "%GOOGLE_KEY%"
    echo ✓ GOOGLE_MAPS_API_KEY set
) else (
    echo ⚠ GOOGLE_MAPS_API_KEY skipped
)

set /p ATTOM_KEY="ATTOM API Key: "
if not "%ATTOM_KEY%"=="" (
    setx ATTOM_API_KEY "%ATTOM_KEY%"
    echo ✓ ATTOM_API_KEY set
) else (
    echo ⚠ ATTOM_API_KEY skipped
)

echo.
echo ===============================================
echo  INSTALLATION COMPLETE
echo ===============================================
echo.

echo Environment variables have been set. You need to:
echo.
echo 1. RESTART your command prompt/terminal
echo 2. RESTART the job worker (if running)
echo 3. RESTART the Next.js development server (if running)
echo.
echo The address enrichment will now automatically run during record pulling.
echo.
echo To verify the setup, check that these environment variables are set:
echo   - SMARTYSTREETS_AUTH_ID
echo   - SMARTYSTREETS_AUTH_TOKEN
echo   - ATTOM_API_KEY
echo   - GOOGLE_MAPS_API_KEY (optional fallback)
echo.

echo ===============================================
echo  TESTING THE SETUP
echo ===============================================
echo.

echo To test address enrichment, you can:
echo.
echo 1. Pull new records from the dashboard
echo 2. Check that property_address field contains full addresses with:
echo    - Street number and name
echo    - City, State, ZIP+4 code
echo    - Proper SmartyStreets validation
echo.
echo 3. Test Skip Trace and Hot 20 features - they should now work better
echo    with the enriched addresses
echo.
echo 4. SmartyStreets provides the most accurate US address validation
echo    including ZIP+4 codes for better mail delivery and data quality
echo.

echo ===============================================
echo  API PRICING INFO
echo ===============================================
echo.
echo SmartyStreets US Street API pricing:
echo - Pay-as-you-go: $0.30 per 1,000 lookups
echo - Monthly plans available with volume discounts
echo - More accurate than USPS with ZIP+4 support
echo - Handles apartment/unit numbers better
echo.

pause 
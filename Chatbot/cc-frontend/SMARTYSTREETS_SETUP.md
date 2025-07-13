# SmartyStreets Address Enrichment Setup

## Overview
Your system has been configured to use SmartyStreets US Autocomplete & ZIP+4 API for address enrichment during record pulling. This provides the most accurate US address validation and standardization.

## Quick Setup

### For macOS/Linux Users
```bash
cd Chatbot/cc-frontend
./setup-address-enrichment.sh
```

### For Windows Users
```cmd
cd Chatbot\cc-frontend
setup-address-enrichment.bat
```

## Environment Variables Required

### SmartyStreets API Keys (Primary)
```bash
SMARTYSTREETS_AUTH_ID=your_auth_id_here
SMARTYSTREETS_AUTH_TOKEN=your_auth_token_here
```

### Other Required Keys
```bash
ATTOM_API_KEY=your_attom_api_key_here
```

### Optional Fallback
```bash
GOOGLE_MAPS_API_KEY=your_google_maps_key_here  # Optional fallback
```

## Getting SmartyStreets API Keys

1. Go to https://www.smartystreets.com/
2. Sign up for an account
3. Navigate to your dashboard
4. Create a new API key for "US Street Address API"
5. Copy your Auth ID and Auth Token (not a single API key, but two separate values)

## Manual Setup (Alternative)

### macOS/Linux (Terminal)
```bash
# Add to ~/.zshrc (for zsh) or ~/.bash_profile (for bash)
export SMARTYSTREETS_AUTH_ID="your_auth_id_here"
export SMARTYSTREETS_AUTH_TOKEN="your_auth_token_here"
export ATTOM_API_KEY="your_attom_api_key_here"
export GOOGLE_MAPS_API_KEY="your_google_maps_key_here"  # Optional

# Then reload your shell
source ~/.zshrc  # or source ~/.bash_profile
```

### Windows (Command Prompt)
```cmd
set SMARTYSTREETS_AUTH_ID=your_auth_id_here
set SMARTYSTREETS_AUTH_TOKEN=your_auth_token_here
set ATTOM_API_KEY=your_attom_api_key_here
set GOOGLE_MAPS_API_KEY=your_google_maps_key_here
```

### Windows (PowerShell)
```powershell
$env:SMARTYSTREETS_AUTH_ID="your_auth_id_here"
$env:SMARTYSTREETS_AUTH_TOKEN="your_auth_token_here"
$env:ATTOM_API_KEY="your_attom_api_key_here"
$env:GOOGLE_MAPS_API_KEY="your_google_maps_key_here"
```

### Windows (Permanent - System Properties)
1. Open System Properties → Advanced → Environment Variables
2. Add new system variables:
   - Name: `SMARTYSTREETS_AUTH_ID`, Value: `your_auth_id_here`
   - Name: `SMARTYSTREETS_AUTH_TOKEN`, Value: `your_auth_token_here`
   - Name: `ATTOM_API_KEY`, Value: `your_attom_api_key_here`
   - Name: `GOOGLE_MAPS_API_KEY`, Value: `your_google_maps_key_here` (optional)

## How It Works

1. **During Record Pulling**: When you pull records from the dashboard, each property address is automatically enriched
2. **SmartyStreets Validation**: Raw addresses are validated and standardized using SmartyStreets
3. **ATTOM Data Enhancement**: Property data (equity, loan info, owner details) is added using ATTOM API
4. **Database Storage**: Only the enriched/canonical addresses are stored in the database
5. **Skip Trace Ready**: Enriched addresses work better with skip trace and chat APIs

## Address Enrichment Pipeline Features

- **Address Standardization**: Converts "123 main st" → "123 Main St, City, ST 12345-6789"
- **ZIP+4 Codes**: Adds full ZIP+4 postal codes for precise location
- **Property Valuation**: Estimates current market value and loan balances
- **Equity Calculation**: Calculates available equity and loan-to-value ratios
- **Owner Information**: Attempts to find owner names and contact information
- **Geocoding**: Provides latitude/longitude coordinates

## Testing the Setup

1. Set up your environment variables using one of the methods above
2. Pull records from the dashboard
3. Check the `property_address` field - it should show standardized addresses
4. Use Skip Trace on any record to see the enriched data
5. Check the logs at `Chatbot/cc-frontend/scripts/address_enrichment.log`

## Troubleshooting

### Common Issues
- **"API key not found"**: Check that environment variables are set correctly
- **"Address validation failed"**: SmartyStreets couldn't parse the address - will fall back to Google Maps
- **"ATTOM data not found"**: Property not in ATTOM database - equity data will be empty
- **Rate limiting**: APIs have rate limits - the system will automatically retry

### Checking Environment Variables
```bash
# macOS/Linux
echo $SMARTYSTREETS_AUTH_ID
echo $SMARTYSTREETS_AUTH_TOKEN
echo $ATTOM_API_KEY

# Windows Command Prompt
echo %SMARTYSTREETS_AUTH_ID%
echo %SMARTYSTREETS_AUTH_TOKEN%
echo %ATTOM_API_KEY%

# Windows PowerShell
echo $env:SMARTYSTREETS_AUTH_ID
echo $env:SMARTYSTREETS_AUTH_TOKEN
echo $env:ATTOM_API_KEY
```

## API Costs

- **SmartyStreets**: ~$0.50 per 1,000 addresses (very affordable)
- **ATTOM**: Varies by plan, typically $0.10-$0.50 per property lookup
- **Google Maps**: $5 per 1,000 requests (fallback only)

## Support

If you encounter issues:
1. Check the logs at `scripts/address_enrichment.log`
2. Verify your API keys are correct and active
3. Test with a small batch of records first
4. Contact support with specific error messages

## Next Steps

Once set up, your record pulling will automatically:
1. ✅ Validate and standardize all addresses
2. ✅ Add property valuation and equity data
3. ✅ Store only clean, enriched addresses
4. ✅ Improve skip trace and chat API accuracy
5. ✅ Provide better lead qualification data 
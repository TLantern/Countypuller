# Google Maps API Setup for Skip Trace

## Step 1: Get Google Maps API Key

1. **Go to Google Cloud Console**: https://console.cloud.google.com/
2. **Create/Select Project**: 
   - Create a new project called "CountyPuller" or use existing
3. **Enable Geocoding API**:
   - Go to "APIs & Services" > "Library"
   - Search for "Geocoding API"
   - Click "Enable"
4. **Create API Key**:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "API Key"
   - Copy the API key (starts with `AIza...`)

## Step 2: Set Environment Variable

**Set the API key permanently on Windows:**

```powershell
# Run as Administrator in PowerShell
[Environment]::SetEnvironmentVariable("GOOGLE_MAPS_API_KEY", "YOUR_API_KEY_HERE", "User")
```

Replace `YOUR_API_KEY_HERE` with your actual Google Maps API key.

## Step 3: Restart Your Terminal

**Important**: After setting the environment variable, restart your PowerShell/terminal and your dev server.

```powershell
# Restart your dev server
./Start-Dev
```

## Step 4: Test Skip Trace

1. Go to your dashboard in the browser
2. Click any "Trace" button next to an address
3. You should now see successful address validation!

## Pricing

- **Free tier**: 200 requests per month
- **Paid**: $5 per 1,000 requests after free tier
- **Your usage**: Probably 1-10 requests per day = FREE

## Benefits vs USPS

✅ **Instant setup** (no waiting for approval)  
✅ **Higher accuracy** (~95% vs ~85%)  
✅ **Better reliability** (99.9% uptime)  
✅ **Handles variations** (abbreviations, typos)  
✅ **Includes coordinates** (bonus feature)

## Fallback

If Google Maps is unavailable, the system automatically falls back to USPS (if you have USPS_USER_ID set). 
# Skip Trace Setup Guide

## Overview
The skip trace functionality has been successfully integrated into your dashboard. It enriches property addresses with ATTOM data including loan balance, equity, and LTV ratios.

## ✅ What's Been Implemented

### 1. Backend Infrastructure
- **Address Enrichment Pipeline** (`scripts/address_enrichment_pipeline.py`)
  - Google Maps Geocoding API for address validation (primary)
  - USPS API fallback support
  - ATTOM Property API integration for property data
  - Comprehensive error handling and retry logic

### 2. API Endpoint
- **Skip Trace API** (`/api/skip-trace/route.ts`)
  - Processes single addresses from dashboard rows
  - Creates temporary CSV files for pipeline processing
  - Returns enriched property data
  - Automatic cleanup of temporary files

### 3. Dashboard Integration
- **Skip Trace Button** added to all data tables:
  - LPH Records
  - Maryland Case Search
  - Hillsborough NH Records
  - Brevard FL Records
  - Fulton GA Records
  - Cobb GA Records
- **Loading States** and **Result Modals**
- **TypeScript Support** for csv-parser

## 🔧 Required API Setup

### Google Maps API Key Configuration

**Current Issue**: Your API key has HTTP referrer restrictions that prevent server-side usage.

**Solutions**:
1. **Option A (Recommended)**: Create a new API key without restrictions
   - Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
   - Create a new API key
   - Enable "Geocoding API" 
   - Set restriction to "None" or "IP addresses" (add your server IPs)

2. **Option B**: Modify existing key
   - Go to your existing API key settings
   - Change "Application restrictions" from "HTTP referrers" to "None"

### Environment Variables

Set these environment variables:

```bash
# Google Maps (Primary address validation)
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here

# ATTOM (Property data enrichment) 
ATTOM_API_KEY=your_attom_api_key_here

# USPS (Fallback address validation) - Optional
USPS_USER_ID=your_usps_user_id_here
```

**Windows PowerShell**:
```powershell
$env:GOOGLE_MAPS_API_KEY = "your_api_key_here"
$env:ATTOM_API_KEY = "your_attom_api_key_here"
```

**Permanent Windows Environment Variables**:
```powershell
[Environment]::SetEnvironmentVariable("GOOGLE_MAPS_API_KEY", "your_api_key_here", "User")
[Environment]::SetEnvironmentVariable("ATTOM_API_KEY", "your_attom_api_key_here", "User")
```

## 🧪 Testing

### Test Google Maps API
```bash
cd scripts
python test_google_maps_api.py
```

### Test Complete Pipeline
```bash
cd scripts
python test_complete_pipeline.py
```

### Test Skip Trace in Browser
1. Start development server: `npm run dev`
2. Navigate to Dashboard
3. Click "Skip Trace" button on any property row
4. Check browser console for detailed error messages

## 📊 Expected Results

When working properly, skip trace will return:
- **ATTOM ID**: Unique property identifier
- **Loan Balance**: Current estimated loan amount
- **Available Equity**: Property value minus loan balance
- **LTV Ratio**: Loan-to-value percentage

## 🚨 Current Status

- ✅ **Infrastructure**: Complete and tested
- ✅ **Dashboard Integration**: Fully implemented
- ⚠️ **Google Maps API**: Restricted key (needs unrestricted key)
- ❓ **ATTOM API**: Needs valid API key for testing
- ✅ **Error Handling**: Comprehensive logging and fallbacks

## 🔄 Next Steps

1. **Fix Google Maps API**: Create unrestricted API key
2. **Get ATTOM API Key**: Sign up at [ATTOM Data](https://api.attomdata.com/)
3. **Test End-to-End**: Verify complete functionality
4. **Deploy to Production**: Update environment variables on server

## 📁 Key Files

- `scripts/address_enrichment_pipeline.py` - Main processing logic
- `src/app/api/skip-trace/route.ts` - API endpoint
- `src/app/dashboard/page.tsx` - Dashboard with skip trace buttons
- `scripts/test_google_maps_api.py` - Google Maps testing
- `scripts/test_complete_pipeline.py` - End-to-end testing

## 💡 Troubleshooting

**"REQUEST_DENIED" from Google Maps**:
- API key has referrer restrictions
- Geocoding API not enabled
- Billing not configured

**"No ATTOM ID found"**:
- Invalid ATTOM API key
- Address format not recognized by ATTOM
- Property not in ATTOM database

**Skip trace returns null values**:
- Check browser console for specific errors
- Verify environment variables are set
- Check server logs for pipeline errors 
# Address Enrichment Pipeline

A batch pipeline that enriches U.S. street addresses with ATTOM property data including current loan balance, LTV (Loan-to-Value), and available equity. Results are saved to both CSV and optionally to a PostgreSQL database.

## Features

✅ **Address Normalization**: Uses USPS Address Validation API to standardize addresses  
✅ **ATTOM Property Lookup**: Retrieves property IDs using ATTOM's property summary endpoint  
✅ **Equity Data Enrichment**: Gets loan balance, LTV, and available equity from ATTOM's homeequity endpoint  
✅ **Batch Processing**: Handles multiple addresses with configurable concurrency  
✅ **Rate Limiting**: Respects ATTOM's 10 requests/second burst limit  
✅ **Resilient**: Exponential backoff retry logic for API failures  
✅ **Dual Output**: Saves to CSV and optionally upserts to PostgreSQL  
✅ **Comprehensive Logging**: Detailed logs for monitoring and debugging  

## Quick Start

### 1. Setup Environment

```bash
# Install dependencies
pip install -r requirements_address_enrichment.txt

# Set API credentials
set USPS_USER_ID=your_usps_user_id
set ATTOM_API_KEY=your_attom_api_key
```

### 2. Prepare Input Data

Create a CSV file with an `address` column:

```csv
address
1600 Pennsylvania Avenue NW, Washington, DC 20500
123 Main Street, Anytown, NY 12345
456 Oak Avenue Unit 2B, Los Angeles, CA 90210
```

### 3. Run Pipeline

```bash
# Basic usage
python address_enrichment_pipeline.py input.csv

# With custom output and PostgreSQL
python address_enrichment_pipeline.py input.csv --output enriched.csv --pg-dsn "postgresql://user:pass@localhost/db"

# With specific calculation date and concurrency
python address_enrichment_pipeline.py input.csv --calc-date 2024-01-01 --max-concurrent 5
```

## API Requirements

### USPS Web Tools API

1. Register at [USPS Web Tools](https://www.usps.com/business/web-tools-apis/)
2. Get your User ID for the Address Validation API
3. Set `USPS_USER_ID` environment variable

### ATTOM Data API

1. Sign up at [ATTOM Data](https://api.developer.attomdata.com/)
2. Subscribe to these endpoints:
   - Property API (property/summary)
   - Valuation API (valuation/homeequity)
3. Set `ATTOM_API_KEY` environment variable

## Pipeline Workflow

### Step 1: Address Normalization
- **Input**: Raw address string
- **Process**: Parse and validate using USPS API
- **Output**: Canonical standardized address
- **Storage**: Both `raw_address` and `canonical_address` are preserved

### Step 2: Property ID Lookup
- **Input**: Canonical address
- **Process**: Query ATTOM property/summary endpoint
- **Output**: ATTOM property ID
- **Rate Limit**: ≤10 requests/second

### Step 3: Equity Data Retrieval
- **Input**: ATTOM property ID
- **Process**: Query ATTOM valuation/homeequity endpoint
- **Output**: Loan balance, LTV, available equity
- **Handles**: Multiple loans (uses first loan's data)

## Output Schema

### CSV Output
```csv
raw_address,canonical_address,attomid,est_balance,available_equity,ltv,loans_count,processed_at
"123 main st, houston tx","123 MAIN ST, HOUSTON, TX 77001-1234",12345678,245000.00,85000.00,0.74,1,"2024-01-15T10:30:00"
```

### PostgreSQL Schema
```sql
CREATE TABLE loan_snapshot (
    attomid          BIGINT PRIMARY KEY,
    est_balance      NUMERIC,
    available_equity NUMERIC,
    ltv              NUMERIC,
    pulled_at        TIMESTAMPTZ DEFAULT now()
);
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `input_csv` | Input CSV file with addresses | Required |
| `--output` | Output CSV filename | `output.csv` |
| `--pg-dsn` | PostgreSQL connection string | None |
| `--calc-date` | Equity calculation date (YYYY-MM-DD) | Today |
| `--max-concurrent` | Max concurrent API requests | 10 |

## Error Handling

### Address Validation Failures
- **Fallback**: Uses original address if USPS validation fails
- **Logging**: Warns about validation issues but continues processing

### ATTOM API Failures
- **Retries**: Exponential backoff with max 3 attempts
- **Rate Limiting**: Automatic rate limiting to respect API limits
- **Missing Data**: Gracefully handles properties without loans or equity data

### Network Issues
- **Timeouts**: 30-second timeout per request
- **Connection Pooling**: Efficient HTTP connection reuse
- **Graceful Degradation**: Continues processing other addresses if individual requests fail

## Rate Limiting & Performance

- **ATTOM API Limit**: 10 requests/second burst limit
- **Concurrency**: Default 10 concurrent requests (configurable)
- **Performance**: ~100-500 addresses per minute depending on API response times
- **Memory Usage**: Efficient streaming processing for large datasets

## Logging

All operations are logged to both console and `address_enrichment.log`:

```
2024-01-15 10:30:15 - INFO - Loaded 100 addresses from input.csv
2024-01-15 10:30:16 - INFO - USPS validated: '123 main st houston tx' -> '123 MAIN ST, HOUSTON, TX 77001-1234'
2024-01-15 10:30:17 - INFO - Found ATTOM ID 12345678 for '123 MAIN ST, HOUSTON, TX 77001-1234'
2024-01-15 10:30:18 - INFO - Retrieved equity data for ATTOM ID 12345678
2024-01-15 10:35:22 - INFO - Completed batch enrichment. 100 results generated.
```

## Example Use Cases

### Real Estate Investment Analysis
```bash
# Analyze a portfolio of properties for equity extraction opportunities
python address_enrichment_pipeline.py portfolio.csv --output equity_analysis.csv
```

### Loan Origination Pipeline
```bash
# Enrich loan applications with current property values and existing debt
python address_enrichment_pipeline.py loan_applications.csv --pg-dsn $DATABASE_URL
```

### Market Research
```bash
# Study LTV ratios across different markets with historical calculation date
python address_enrichment_pipeline.py market_sample.csv --calc-date 2023-01-01
```

## Troubleshooting

### Common Issues

**"USPS_USER_ID environment variable is required"**
- Solution: Set your USPS API user ID: `set USPS_USER_ID=your_user_id`

**"No address column found"**
- Solution: Ensure your CSV has a column named `address`, `street_address`, `property_address`, or `full_address`

**"Rate limited on ATTOM API"**
- Solution: Reduce `--max-concurrent` parameter (try 3-5 for free tier accounts)

**"No ATTOM ID found"**
- Solution: Address may not exist in ATTOM database or may need manual correction

### Performance Tuning

1. **Reduce Concurrency**: Lower `--max-concurrent` if hitting rate limits
2. **Batch Size**: Process large datasets in smaller chunks if memory is limited
3. **API Tier**: Upgrade ATTOM subscription for higher rate limits

## Data Quality Notes

### Address Matching
- USPS validation improves ATTOM match rates significantly
- Some addresses may not exist in ATTOM's database
- Commercial properties may have limited loan data

### Loan Data Accuracy
- `est_balance` represents amortized loan balance estimate
- Multiple loans are common; pipeline uses first loan data
- LTV calculations are based on current property values

### Temporal Considerations
- Equity data reflects values as of calculation date
- Property values and loan balances change over time
- Historical analysis requires appropriate `--calc-date` parameter

## Contributing

To extend the pipeline:

1. **Additional APIs**: Add new enrichment sources in `AddressEnrichmentPipeline` class
2. **Output Formats**: Extend `save_to_*` functions for new output types
3. **Address Parsing**: Improve `normalize_address_for_usps` for better parsing
4. **Error Handling**: Add specific error handling for new failure modes

## License

This pipeline is part of the Clerk Crawler project. Ensure compliance with USPS and ATTOM API terms of service. 
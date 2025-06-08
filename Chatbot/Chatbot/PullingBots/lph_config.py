from config_schemas import CountyConfig, FieldMapping, SelectorConfig, ScraperType, PaginationType, SearchConfig, PaginationConfig, FieldType

lph_config = CountyConfig(
    name="Harris County Lis Pendens",
    state="TX",
    base_url="https://www.cclerk.hctx.net/Applications/WebSearch/RP.aspx",
    scraper_type=ScraperType.SEARCH_FORM,
    headless=False,
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    timeout=30,
    delay_between_requests=2,
    required_fields=["case_number", "file_date", "document_type"],
    max_records=10,  # Limit to 10 records
    field_mappings=[
        FieldMapping(
            field_name="case_number",
            field_type=FieldType.CASE_NUMBER,
            selectors=[
                SelectorConfig(selector="td:nth-child(2)", selector_type="css", attribute="text")  # Skip first td, case number in 2nd
            ]
        ),
        FieldMapping(
            field_name="file_date", 
            field_type=FieldType.DATE,
            selectors=[
                SelectorConfig(selector="td:nth-child(3)", selector_type="css", attribute="text")  # Date in 3rd column
            ]
        ),
        FieldMapping(
            field_name="document_type",
            field_type=FieldType.TEXT,
            selectors=[
                SelectorConfig(selector="td:nth-child(4)", selector_type="css", attribute="text")  # Document type in 4th column
            ]
        ),

        FieldMapping(
            field_name="names_grantor_grantee",
            field_type=FieldType.TEXT,
            selectors=[
                SelectorConfig(selector="td:nth-child(5) table td", selector_type="css", attribute="text")  # Names in nested table in 5th column
            ]
        ),
        FieldMapping(
            field_name="legal_description", 
            field_type=FieldType.TEXT,
            selectors=[
                SelectorConfig(selector="td:nth-child(6) table td", selector_type="css", attribute="text")  # Legal desc in nested table in 6th column
            ]
        ),
        FieldMapping(
            field_name="property_address",
            field_type=FieldType.ADDRESS,
            selectors=[
                SelectorConfig(selector="td:last-child a", selector_type="css", attribute="href")  # Will use OCR from film link
            ],
            requires_ocr=True  # This will trigger OCR extraction from film code link to get actual address
        ),
    ],
    search_config=SearchConfig(
        search_url="https://www.cclerk.hctx.net/Applications/WebSearch/RP.aspx",
        search_form_selector="form",  # TODO: Update with actual selector
        search_fields={
            "date_from": "input[name='ctl00$ContentPlaceHolder1$txtFrom']",      # Date from field (flexible range)
            "date_to": "input[name='ctl00$ContentPlaceHolder1$txtTo']",          # Date to field (flexible range)
            "search_term": "input[name='ctl00$ContentPlaceHolder1$txtInstrument']"  # Instrument type field for L/P
        },
        submit_button_selector="input[name*='btnSearch']",  # Updated based on common patterns
        results_container_selector="#itemPlaceholderContainer"  # Target the main results table
    ),
    pagination_config=PaginationConfig(
        pagination_type=PaginationType.NEXT_PREVIOUS,
        next_button_selector="a[href*='Page$Next']",  # Updated based on common patterns
        max_pages=10
    )
) 
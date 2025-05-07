import time
import random
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

# -------------------------------------
# CONFIG: User credentials
USERNAME = "TeniolaTheGreat"
PASSWORD = "StackBread2@"
# -------------------------------------

# List of user agents to randomize
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
]

# Set up Chrome options (disable headless for debugging if needed)
options = Options()
# options.add_argument('--headless')  # Uncomment to run headless
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument(f'--user-agent={random.choice(user_agents)}')

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 10)

# --------------------- PHASE 1: Scrape Main Listing ---------------------
main_url = "https://www.cclerk.hctx.net/Applications/WebSearch/RP.aspx"
driver.get(main_url)
time.sleep(random.uniform(3, 6))

try:
     # 1. Enter "NOTICE" in the Instrument Type field
    instrument_input = wait.until(EC.presence_of_element_located(
        (By.ID, "ctl00_ContentPlaceHolder1_txtInstrument")
    ))
    instrument_input.clear()
    instrument_input.send_keys("NOTICE")

    # 2. Set "Date (From)" to 04/16/2025
    from_input = wait.until(EC.presence_of_element_located(
        (By.ID, "ctl00_ContentPlaceHolder1_txtFrom")
    ))
    from_input.clear()
    from_input.send_keys("04/16/2025")

    # 3. Set "Date (To)" to 04/23/2025
    to_input = wait.until(EC.presence_of_element_located(
        (By.ID, "ctl00_ContentPlaceHolder1_txtTo")
    ))
    to_input.clear()
    to_input.send_keys("04/23/2025")

    # 4. Click the "Search" button
    search_btn = wait.until(EC.element_to_be_clickable(
        (By.ID, "ctl00_ContentPlaceHolder1_btnSearch")
    ))
    search_btn.click()

    # 5. Wait for the results grid to load
    wait.until(EC.presence_of_element_located(
        (By.ID, "ctl00_ContentPlaceHolder1_GridView1")
    ))
    print("✅ Search for NOTICE between 04/16/2025 and 04/23/2025 executed successfully.")

except Exception as e:
    print(f"❌ Error during search for NOTICE with date range: {e}")

# -------------------------------------
    # PHASE 2: Collect Detail URLs
    # -------------------------------------
    rows = driver.find_elements(By.XPATH, "//table[@id='ctl00_ContentPlaceHolder1_GridView1']//tr[td]")
    print(f"🔍 Found {len(rows)} result rows")
    links = []
    for row in rows:
        try:
            a = row.find_element(By.TAG_NAME, 'a')
            links.append(a.get_attribute('href'))
        except:
            continue

    if not links:
        print("❌ No detail links found — check that the grid ID and XPaths match the live page structure.")

    # -------------------------------------
    # PHASE 3: Scrape Detail Pages
    # -------------------------------------
    records = []
    def get_text_by_label(lbl):
        try:
            el = driver.find_element(By.XPATH, f"//label[text()='{lbl}']/following-sibling::*[1]")
            return el.text.strip()
        except:
            return ""

    for url in links:
        driver.execute_script("window.open(arguments[0], '_blank');", url)
        driver.switch_to.window(driver.window_handles[-1])
        wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        time.sleep(random.uniform(1,2))

        file_number    = get_text_by_label('File Number')
        file_date      = get_text_by_label('File Date')
        volume         = get_text_by_label('Volume')
        page           = get_text_by_label('Page')
        legal_desc     = get_text_by_label('Legal Description')
        
        try:
            fc = driver.find_element(By.XPATH, "//label[text()='Film Code']/following-sibling::a")
            film_code_link = fc.get_attribute('href')
        except:
            film_code_link = ""

        names = []
        try:
            tbl = driver.find_element(By.XPATH, "//label[text()='Grantor']/ancestor::div[1]//table")
            for tr in tbl.find_elements(By.TAG_NAME, 'tr'):
                cells = [td.text.strip() for td in tr.find_elements(By.TAG_NAME, 'td')]
                if cells:
                    names.append(cells)
        except:
            pass

        records.append({
            'File Number': file_number,
            'File Date': file_date,
            'Volume': volume,
            'Page': page,
            'Film Code Link': film_code_link,
            'Names & Grantors': names,
            'Legal Description': legal_desc
        })

        # Close this tab and return to main
        driver.close()
        driver.switch_to.window(driver.window_handles[0])

    # -------------------------------------
    # PHASE 4: Save Data
    # -------------------------------------
    df = pd.DataFrame(records)
    df.to_csv('harris_notice_details.csv', index=False)
    print(f"✅ Scraped {len(records)} records with full details.")

finally:
    driver.quit()

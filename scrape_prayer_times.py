# --- START OF FILE scrape_prayer_times.py ---

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
from datetime import datetime, date, timedelta
import pytz
from config_loader import load_config
import os
import sys
import urllib.parse

# Load configuration
try:
    config = load_config()
except Exception as e:
    print(f"FATAL: Could not load configuration for prayer time scraping: {e}")
    sys.exit(1)

BRAVE_PATH = config.get('brave_path')
BASE_URL = config.get('muwaqqit_base_url')
TARGET_TIMEZONE_STR = config.get('target_timezone') # Used as a fallback
PRAYER_DEFINITIONS = config.get('prayer_definitions')
TIMEOUT_CONFIG = config.get('timeouts', {})
OVERALL_PROCESS_TIMEOUT_SECONDS = TIMEOUT_CONFIG.get('overall_process_seconds', 60.0)
PAGE_LOAD_TIMEOUT_SECONDS = TIMEOUT_CONFIG.get('page_load_seconds', 25.0)
ADDITIONAL_DELAY_SECONDS = TIMEOUT_CONFIG.get('additional_delay_seconds', 5.0)

# USER_LOCATION_ADDRESS is no longer directly used here for URL construction, it's part of location_params if provided as a fallback.
# We'll still load it for the critical config check for completeness.
USER_LOCATION_ADDRESS_FALLBACK = config.get('user_location_address')

critical_scraper_configs = {
    "muwaqqit_base_url": BASE_URL,
    "target_timezone": TARGET_TIMEZONE_STR,
    "prayer_definitions": PRAYER_DEFINITIONS,
    "user_location_address": USER_LOCATION_ADDRESS_FALLBACK # Check it exists in config
}
for key, value in critical_scraper_configs.items():
    if value is None:
        print(f"FATAL: Scraper critical configuration key '{key}' is missing in config.json. Exiting.")
        sys.exit(1)

ALL_TIME_LABELS_TO_SCRAPE = set()
if PRAYER_DEFINITIONS:
    for prayer_key, definition in PRAYER_DEFINITIONS.items():
        ALL_TIME_LABELS_TO_SCRAPE.add(definition.get("start_text"))
        ALL_TIME_LABELS_TO_SCRAPE.add(definition.get("end_text"))
ALL_TIME_LABELS_TO_SCRAPE = {label for label in ALL_TIME_LABELS_TO_SCRAPE if label is not None}


def get_prayer_times_with_ends(target_date_obj_override=None, location_params=None):
    """
    Scrapes prayer start and end times from the configured website for a specific date and location.

    Args:
        target_date_obj_override (datetime.date, optional): Date to scrape for.
        location_params (dict, optional): Dictionary containing location info.
            Expected keys:
            - "latitude", "longitude", "timezone" (for IP-based location)
            OR
            - "address", "timezone" (for address-based fallback)
            If None, or missing keys, uses TARGET_TIMEZONE_STR and USER_LOCATION_ADDRESS_FALLBACK from config.

    Returns:
        dict or None: Prayer schedule or None on failure/interruption.
    """
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--log-level=3")

    driver = None
    prayer_schedule = {
        prayer_key: {"start": None, "end": None, "start_date_offset": 0, "end_date_offset": 0, "date_for_start": None, "date_for_end": None}
        for prayer_key in PRAYER_DEFINITIONS.keys()
    } if PRAYER_DEFINITIONS else {}
    scraped_times_raw = {label: None for label in ALL_TIME_LABELS_TO_SCRAPE}
    function_start_time = time.time()

    try:
        # Determine operational location and timezone
        op_latitude = None
        op_longitude = None
        op_timezone_str = TARGET_TIMEZONE_STR # Default fallback
        op_address_for_display = USER_LOCATION_ADDRESS_FALLBACK # Default fallback

        if location_params:
            op_timezone_str = location_params.get("timezone", TARGET_TIMEZONE_STR)
            if "latitude" in location_params and "longitude" in location_params:
                op_latitude = location_params.get("latitude")
                op_longitude = location_params.get("longitude")
                op_address_for_display = location_params.get("address_for_display", f"Lat/Lon: {op_latitude},{op_longitude}")
            elif "address" in location_params:
                # If only address is provided (fallback scenario)
                op_address_for_display = location_params.get("address", USER_LOCATION_ADDRESS_FALLBACK)
            else: # Should not happen if prayer_calendar_manager prepares location_params correctly
                print("Warning: location_params provided but missing expected keys. Using fallbacks.")
        
        current_op_timezone = pytz.timezone(op_timezone_str)

        base_date_obj_for_url = None
        if target_date_obj_override:
            base_date_obj_for_url = target_date_obj_override
            print(f"Scraper called with target date override: {base_date_obj_for_url.strftime('%Y-%m-%d')}")
        else:
            current_datetime = datetime.now(current_op_timezone)
            base_date_obj_for_url = current_datetime.date()
        date_to_fetch_str = base_date_obj_for_url.strftime("%Y-%m-%d")

        # --- DYNAMIC URL CONSTRUCTION ---
        url_params = []
        if op_latitude is not None and op_longitude is not None:
            url_params.append(f"lt={op_latitude}")
            url_params.append(f"ln={op_longitude}")
            # When providing lat/lon, muwaqqit.com still benefits from an explicit timezone.
            url_params.append(f"tz={urllib.parse.quote_plus(op_timezone_str)}")
        elif "address" in location_params: # Fallback to using address from location_params
            url_params.append(f"add={urllib.parse.quote_plus(location_params['address'])}")
            url_params.append(f"tz={urllib.parse.quote_plus(op_timezone_str)}")
        else: # Extreme fallback to USER_LOCATION_ADDRESS_FALLBACK from config
            url_params.append(f"add={urllib.parse.quote_plus(USER_LOCATION_ADDRESS_FALLBACK)}")
            url_params.append(f"tz={urllib.parse.quote_plus(TARGET_TIMEZONE_STR)}")


        url_params.append(f"d={date_to_fetch_str}")
        url_to_scrape = f"{BASE_URL}&{'&'.join(url_params)}"
        # --------------------------------

        print(f"Fetching times for location \"{op_address_for_display}\" (Timezone: {op_timezone_str}) for date: {date_to_fetch_str}")

        service = None
        if BRAVE_PATH and os.path.exists(BRAVE_PATH):
            print(f"Using Brave browser from: {BRAVE_PATH}")
            options.binary_location = BRAVE_PATH
            service = ChromeService()
        else:
            print("Setting up ChromeDriver using webdriver-manager (Brave path not specified or invalid)...")
            service = ChromeService(ChromeDriverManager().install())

        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT_SECONDS)

        print(f"Navigating to URL: {url_to_scrape}")
        try:
            driver.get(url_to_scrape)
            print("Page navigation initiated by driver.get().")
        except TimeoutException:
            current_elapsed = time.time() - function_start_time
            if current_elapsed > OVERALL_PROCESS_TIMEOUT_SECONDS:
                 raise TimeoutException(f"Overall timeout ({OVERALL_PROCESS_TIMEOUT_SECONDS}s) exceeded during initial page load which itself timed out.")
            print(f"driver.get() timed out after {PAGE_LOAD_TIMEOUT_SECONDS}s, but continuing within overall budget if possible...")
        except KeyboardInterrupt:
            print("\nScraping interrupted during page navigation by user (Ctrl+C).")
            return None

        current_elapsed = time.time() - function_start_time
        if current_elapsed > OVERALL_PROCESS_TIMEOUT_SECONDS:
            raise TimeoutException(f"Overall timeout ({OVERALL_PROCESS_TIMEOUT_SECONDS}s) exceeded after page load attempt.")

        print(f"Adding a fixed delay of {ADDITIONAL_DELAY_SECONDS} seconds...")
        try:
            time.sleep(ADDITIONAL_DELAY_SECONDS)
        except KeyboardInterrupt:
            print("\nScraping interrupted during fixed delay by user (Ctrl+C).")
            return None

        current_elapsed = time.time() - function_start_time
        if current_elapsed > OVERALL_PROCESS_TIMEOUT_SECONDS:
            raise TimeoutException(f"Overall timeout ({OVERALL_PROCESS_TIMEOUT_SECONDS}s) exceeded after fixed delay.")

        table_body_xpath = "//div[@id='results']//table[@class='table']/tbody"
        remaining_time_for_table_wait = max(1, OVERALL_PROCESS_TIMEOUT_SECONDS - current_elapsed)
        print(f"Waiting up to {remaining_time_for_table_wait:.1f}s for table body: {table_body_xpath}")
        wait = WebDriverWait(driver, remaining_time_for_table_wait)

        try:
            table_body = wait.until(EC.presence_of_element_located((By.XPATH, table_body_xpath)))
            print("Table body found.")
        except TimeoutException as te:
            print(f"Timeout Error: {str(te)}")
            if driver:
                try:
                    with open("timeout_page_source.html", "w", encoding="utf-8") as f:
                        f.write(driver.page_source)
                    print("Page source at timeout saved to timeout_page_source.html")
                except Exception as e_save:
                    print(f"Error saving page source: {e_save}")
            return None
        except KeyboardInterrupt:
            print("\nScraping interrupted while waiting for table by user (Ctrl+C).")
            return None

        rows = table_body.find_elements(By.XPATH, "./tr")
        print(f"Found {len(rows)} rows in the table.")

        base_date_obj_for_offsets = base_date_obj_for_url

        for row in rows:
            try:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 3:
                    continue
                prayer_name_element = cells[0].find_element(By.XPATH, ".//b")
                item_label_on_page = prayer_name_element.text.strip()
                if item_label_on_page in ALL_TIME_LABELS_TO_SCRAPE:
                    time_cell_text = cells[1].text.strip()
                    actual_time = time_cell_text.split()[0]
                    if '—' in actual_time:
                        actual_time = actual_time.split('—')[0]
                    if ':' in actual_time and len(actual_time.split(':')) == 3:
                        scraped_times_raw[item_label_on_page] = actual_time
                        print(f"Scraped: '{item_label_on_page}' -> {actual_time}")
                        date_cell_text = cells[2].text.strip()
                        date_offset_value = 0
                        if '▲' in date_cell_text: date_offset_value = 1
                        elif '▼' in date_cell_text: date_offset_value = -1
                        if PRAYER_DEFINITIONS:
                            for prayer_key, definition in PRAYER_DEFINITIONS.items():
                                if definition["start_text"] == item_label_on_page:
                                    prayer_schedule[prayer_key]["start_date_offset"] = date_offset_value
                                    prayer_schedule[prayer_key]["date_for_start"] = (base_date_obj_for_offsets + timedelta(days=date_offset_value)).strftime("%Y-%m-%d")
                                if definition["end_text"] == item_label_on_page:
                                    prayer_schedule[prayer_key]["end_date_offset"] = date_offset_value
                                    prayer_schedule[prayer_key]["date_for_end"] = (base_date_obj_for_offsets + timedelta(days=date_offset_value)).strftime("%Y-%m-%d")
                    else:
                        print(f"Warning: Extracted text '{actual_time}' for '{item_label_on_page}' doesn't look like a valid time. Cell text: '{time_cell_text}'")
            except NoSuchElementException: continue
            except Exception as e_row: print(f"Error processing a row: {e_row} - Row HTML: {row.get_attribute('outerHTML')[:200]}")

        all_times_found = True
        if PRAYER_DEFINITIONS:
            for prayer_key, definition in PRAYER_DEFINITIONS.items():
                start_label, end_label = definition["start_text"], definition["end_text"]
                if scraped_times_raw.get(start_label):
                    prayer_schedule[prayer_key]["start"] = scraped_times_raw[start_label]
                    if prayer_schedule[prayer_key]["date_for_start"] is None: prayer_schedule[prayer_key]["date_for_start"] = (base_date_obj_for_offsets + timedelta(days=prayer_schedule[prayer_key]["start_date_offset"])).strftime("%Y-%m-%d")
                else: print(f"Warning: Could not find START time for {prayer_key} (label: '{start_label}')"); all_times_found = False
                if scraped_times_raw.get(end_label):
                    prayer_schedule[prayer_key]["end"] = scraped_times_raw[end_label]
                    if prayer_schedule[prayer_key]["date_for_end"] is None: prayer_schedule[prayer_key]["date_for_end"] = (base_date_obj_for_offsets + timedelta(days=prayer_schedule[prayer_key]["end_date_offset"])).strftime("%Y-%m-%d")
                else: print(f"Warning: Could not find END time for {prayer_key} (label: '{end_label}')"); all_times_found = False
        
        if all_times_found: print("Successfully extracted all required start and end times.")
        else: print("Could not extract all required start and end times. Check warnings.")

    except KeyboardInterrupt: print("\nScraping process interrupted by user (Ctrl+C)."); return None
    except TimeoutException as te: print(f"Timeout Error: {str(te)}"); # ... (rest of existing error handling) ...
    except Exception as e: print(f"An unexpected error occurred during scraping: {e}"); # ... (rest of existing error handling) ...
    finally:
        print("Closing the browser.")
        if driver:
            try: driver.quit()
            except Exception as e_quit: print(f"Error during browser quit: {e_quit}")
    if not all_times_found: return None
    return prayer_schedule


def _test_scraper_functionality():
    """Helper function to test the scraper's direct functionality."""
    print("Attempting to scrape prayer times (defaulting to current Sydney date)...")
    
    # For direct scraper test, use the USER_LOCATION_ADDRESS_FALLBACK and TARGET_TIMEZONE_STR from config
    test_location_params = {
        "address": USER_LOCATION_ADDRESS_FALLBACK,
        "timezone": TARGET_TIMEZONE_STR,
        "address_for_display": f"Test with: {USER_LOCATION_ADDRESS_FALLBACK}"
    }
    schedule_today = get_prayer_times_with_ends(location_params=test_location_params)
    if schedule_today:
        print("\n--- Extracted Prayer Schedule (Today) ---")
        for prayer, times in schedule_today.items():
            print(f"{prayer}: Start: {times.get('start')} on {times.get('date_for_start')}, End: {times.get('end')} on {times.get('date_for_end')}")
    else:
        print("\nFailed to extract complete prayer schedule for today or process was interrupted.")

    print("\nAttempting to scrape for a specific future date...")
    try:
        # For future date test, also use configured address and timezone
        current_op_timezone = pytz.timezone(TARGET_TIMEZONE_STR)
        specific_date_to_test = datetime.now(current_op_timezone).date() + timedelta(days=3)
        
        schedule_future = get_prayer_times_with_ends(
            target_date_obj_override=specific_date_to_test,
            location_params=test_location_params # Use the same test_location_params
        )
        if schedule_future:
            print(f"\n--- Extracted Prayer Schedule ({specific_date_to_test.strftime('%Y-%m-%d')}) ---")
            for prayer, times in schedule_future.items():
                print(f"{prayer}: Start: {times.get('start')} on {times.get('date_for_start')}, End: {times.get('end')} on {times.get('date_for_end')}")
        else:
            print(f"\nFailed to extract complete prayer schedule for {specific_date_to_test.strftime('%Y-%m-%d')} or process was interrupted.")
    except Exception as e_test:
        print(f"Error during future date test in __main__: {e_test}")

if __name__ == '__main__':
    _test_scraper_functionality()

# --- END OF FILE scrape_prayer_times.py ---
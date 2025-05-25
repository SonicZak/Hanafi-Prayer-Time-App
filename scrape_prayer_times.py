# --- START OF FILE scrape_prayer_times.py ---

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager # Make sure this is installed: pip install webdriver-manager
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

# Load configuration
try:
    config = load_config()
except Exception as e:
    print(f"FATAL: Could not load configuration for prayer time scraping: {e}")
    sys.exit(1)

BRAVE_PATH = config.get('brave_path')
BASE_URL = config.get('muwaqqit_base_url')
TARGET_TIMEZONE_STR = config.get('target_timezone')
PRAYER_DEFINITIONS = config.get('prayer_definitions')
TIMEOUT_CONFIG = config.get('timeouts', {})
OVERALL_PROCESS_TIMEOUT_SECONDS = TIMEOUT_CONFIG.get('overall_process_seconds', 60.0)
PAGE_LOAD_TIMEOUT_SECONDS = TIMEOUT_CONFIG.get('page_load_seconds', 25.0)
ADDITIONAL_DELAY_SECONDS = TIMEOUT_CONFIG.get('additional_delay_seconds', 5.0)

critical_scraper_configs = {
    "muwaqqit_base_url": BASE_URL,
    "target_timezone": TARGET_TIMEZONE_STR,
    "prayer_definitions": PRAYER_DEFINITIONS
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


def get_prayer_times_with_ends(target_date_obj_override=None):
    """
    Scrapes prayer start and end times from the configured website for a specific date.

    Uses Selenium to navigate the website, wait for elements, and extract time data.
    Handles date offsets for prayers that might cross midnight (e.g., Isha end).

    Args:
        target_date_obj_override (datetime.date, optional): An optional date object
            to scrape times for. If None, it defaults to the current date in the
            configured target timezone.

    Returns:
        dict or None: A dictionary containing prayer times and associated dates
                      (start, end, date_for_start, date_for_end) for each defined prayer
                      (e.g., Fajr, Zuhr, etc.) if scraping is successful and all
                      required times are found. Returns None if scraping fails
                      or incomplete data is found (including user interruption).
    """
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox") # Critical for sandbox issues
    options.add_argument("--disable-dev-shm-usage") # Often needed in Linux/Docker, can help generally
    options.add_argument("--disable-extensions") # Reduce overhead
    options.add_argument("--disable-browser-side-navigation") # Improve stability
    options.add_argument("--disable-setuid-sandbox") # Another sandbox-related flag
    options.add_argument("--disable-infobars") # Prevent info bars (e.g., "Chrome is being controlled by automated test software")
    options.add_argument("--disable-blink-features=AutomationControlled") # Try to avoid detection
    options.add_experimental_option("excludeSwitches", ["enable-automation"]) # Another anti-detection flag
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
    options.add_argument("--log-level=3")

    driver = None # Initialize driver to None
    scraped_times_raw = {label: None for label in ALL_TIME_LABELS_TO_SCRAPE}
    prayer_schedule = {
        prayer_key: {"start": None, "end": None, "start_date_offset": 0, "end_date_offset": 0, "date_for_start": None, "date_for_end": None}
        for prayer_key in PRAYER_DEFINITIONS.keys()
    } if PRAYER_DEFINITIONS else {}
    
    function_start_time = time.time()

    try: # Main try block for the entire scraping process
        base_date_obj_for_url = None
        if target_date_obj_override:
            base_date_obj_for_url = target_date_obj_override
            print(f"Scraper called with target date override: {base_date_obj_for_url.strftime('%Y-%m-%d')}")
        else:
            sydney_tz = pytz.timezone(TARGET_TIMEZONE_STR)
            current_sydney_datetime = datetime.now(sydney_tz)
            base_date_obj_for_url = current_sydney_datetime.date()

        date_to_fetch_str = base_date_obj_for_url.strftime("%Y-%m-%d")

        url_to_scrape = f"{BASE_URL}&d={date_to_fetch_str}"
        print(f"Fetching times for date ({TARGET_TIMEZONE_STR}): {date_to_fetch_str}")

        service = None # Initialize service to None
        if BRAVE_PATH and os.path.exists(BRAVE_PATH):
            print(f"Using Brave browser from: {BRAVE_PATH}")
            options.binary_location = BRAVE_PATH
            service = ChromeService() # Default service, binary_location handled by options
        else:
            print("Setting up ChromeDriver using webdriver-manager (Brave path not specified or invalid)...")
            service = ChromeService(ChromeDriverManager().install())

        # Now instantiate the driver using the prepared service and options
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
        except KeyboardInterrupt: # Catch Ctrl+C during page load
            print("\nScraping interrupted during page navigation by user (Ctrl+C).")
            return None # Signal interruption

        current_elapsed = time.time() - function_start_time
        if current_elapsed > OVERALL_PROCESS_TIMEOUT_SECONDS:
            raise TimeoutException(f"Overall timeout ({OVERALL_PROCESS_TIMEOUT_SECONDS}s) exceeded after page load attempt.")

        print(f"Adding a fixed delay of {ADDITIONAL_DELAY_SECONDS} seconds...")
        try:
            time.sleep(ADDITIONAL_DELAY_SECONDS)
        except KeyboardInterrupt: # Catch Ctrl+C during sleep
            print("\nScraping interrupted during fixed delay by user (Ctrl+C).")
            return None # Signal interruption

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
        except KeyboardInterrupt: # Catch Ctrl+C while waiting for table
            print("\nScraping interrupted while waiting for table by user (Ctrl+C).")
            return None # Signal interruption


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
                        if '▲' in date_cell_text:
                            date_offset_value = 1
                        elif '▼' in date_cell_text:
                            date_offset_value = -1

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

            except NoSuchElementException:
                continue
            except Exception as e_row:
                print(f"Error processing a row: {e_row} - Row HTML: {row.get_attribute('outerHTML')[:200]}")
                continue

        all_times_found = True
        if PRAYER_DEFINITIONS:
            for prayer_key, definition in PRAYER_DEFINITIONS.items():
                start_label = definition["start_text"]
                end_label = definition["end_text"]

                if scraped_times_raw.get(start_label):
                    prayer_schedule[prayer_key]["start"] = scraped_times_raw[start_label]
                    if prayer_schedule[prayer_key]["date_for_start"] is None:
                         prayer_schedule[prayer_key]["date_for_start"] = (base_date_obj_for_offsets + timedelta(days=prayer_schedule[prayer_key]["start_date_offset"])).strftime("%Y-%m-%d")
                else:
                    print(f"Warning: Could not find START time for {prayer_key} (label: '{start_label}')")
                    all_times_found = False

                if scraped_times_raw.get(end_label):
                    prayer_schedule[prayer_key]["end"] = scraped_times_raw[end_label]
                    if prayer_schedule[prayer_key]["date_for_end"] is None:
                        prayer_schedule[prayer_key]["date_for_end"] = (base_date_obj_for_offsets + timedelta(days=prayer_schedule[prayer_key]["end_date_offset"])).strftime("%Y-%m-%d")
                else:
                    print(f"Warning: Could not find END time for {prayer_key} (label: '{end_label}')")
                    all_times_found = False

        if all_times_found:
            print("Successfully extracted all required start and end times.")
        else:
            print("Could not extract all required start and end times. Check warnings.")

    except KeyboardInterrupt: # Catch any other KeyboardInterrupt in this function
        print("\nScraping process interrupted by user (Ctrl+C).")
        return None # Signal interruption to the caller

    except TimeoutException as te: # This block is for Timeout from wait.until, keep as is
        print(f"Timeout Error: {str(te)}")
        if driver:
            try:
                with open("timeout_page_source.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print("Page source at timeout saved to timeout_page_source.html")
            except Exception as e_save:
                print(f"Error saving page source: {e_save}")
        return None
    except Exception as e: # Generic error catch, ensure KeyboardInterrupt is caught first
        print(f"An unexpected error occurred during scraping: {e}")
        if driver:
            try:
                with open("unexpected_scraper_error_page_source.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print("Page source at unexpected scraper error saved to unexpected_scraper_error_page_source.html")
            except Exception as e_save:
                print(f"Error saving page source during unexpected scraper error: {e_save}")
        return None
    finally:
        # This finally block ensures the browser is closed even if an error or interrupt occurs
        print("Closing the browser.")
        if driver:
            try:
                driver.quit()
            except Exception as e_quit: # Catch any errors that might occur during quit (e.g., if already killed)
                print(f"Error during browser quit: {e_quit}")

    if not all_times_found:
        return None

    return prayer_schedule

def _test_scraper_functionality():
    """Helper function to test the scraper's direct functionality."""
    print("Attempting to scrape prayer times (defaulting to current Sydney date)...")
    schedule_today = get_prayer_times_with_ends()
    if schedule_today:
        print("\n--- Extracted Prayer Schedule (Today) ---")
        for prayer, times in schedule_today.items():
            print(f"{prayer}: Start: {times.get('start')} on {times.get('date_for_start')}, End: {times.get('end')} on {times.get('date_for_end')}")
    else:
        print("\nFailed to extract complete prayer schedule for today or process was interrupted.")

    print("\nAttempting to scrape for a specific future date...")
    try:
        sydney_tz_for_test = pytz.timezone(TARGET_TIMEZONE_STR)
        specific_date_to_test = datetime.now(sydney_tz_for_test).date() + timedelta(days=3)
        schedule_future = get_prayer_times_with_ends(target_date_obj_override=specific_date_to_test)
        if schedule_future:
            print(f"\n--- Extracted Prayer Schedule ({specific_date_to_test.strftime('%Y-%m-%d')}) ---")
            for prayer, times in schedule_future.items(): # This line defines 'times'
                print(f"{prayer}: Start: {times.get('start')} on {times.get('date_for_start')}, End: {times.get('end')} on {times.get('date_for_end')}")
        else:
            print(f"\nFailed to extract complete prayer schedule for {specific_date_to_test.strftime('%Y-%m-%d')} or process was interrupted.")
    except Exception as e_test:
        print(f"Error during future date test in __main__: {e_test}")

if __name__ == '__main__':
    _test_scraper_functionality()

# --- END OF FILE scrape_prayer_times.py ---
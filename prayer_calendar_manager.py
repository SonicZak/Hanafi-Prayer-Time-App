# --- START OF FILE prayer_calendar_manager.py ---

from google_calendar_setup import authenticate_google_calendar, HttpError
from scrape_prayer_times import get_prayer_times_with_ends # This will be called for each day
from datetime import datetime, timedelta, time as dt_time
import pytz
from config_loader import load_config, save_config
import sys
import requests # for IP lookup
from geopy.distance import geodesic # for distance calculation
import urllib.parse

# Load configuration
try:
    config = load_config()
except Exception as e:
    print(f"FATAL: Could not load configuration for Calendar Manager: {e}")
    sys.exit(1)

# Use values from config or provide defaults/raise errors for critical ones
CALENDAR_ID = config.get('calendar_id')
EVENT_REMINDER_MINUTES = config.get('event_reminder_minutes', 0)
TARGET_TIMEZONE_STR = config.get('target_timezone') # Still used as a fallback/default for now
MANAGED_PRAYER_NAMES = config.get('managed_prayer_names')
MUWAQQIT_BASE_URL_FOR_DESC = config.get('muwaqqit_base_url') # Base URL for description, still needed
DAYS_TO_PROCESS_IN_ADVANCE = config.get('processing_days_in_advance', 1)

# --- LOCATION-RELATED CONFIGS ---
LOCATION_CHECK_ENABLED = config.get('location_check_enabled', False)
LOCATION_THRESHOLD_KM = config.get('location_threshold_km', 20.0)
LAST_CHECKED_IP = config.get('last_checked_ip')
LAST_CHECKED_LATITUDE = config.get('last_checked_latitude')
LAST_CHECKED_LONGITUDE = config.get('last_checked_longitude')
LAST_CHECKED_TIMEZONE = config.get('last_checked_timezone')
# ------------------------------------

# Validate critical configurations
critical_configs = {
    "calendar_id": CALENDAR_ID,
    "target_timezone": TARGET_TIMEZONE_STR,
    "managed_prayer_names": MANAGED_PRAYER_NAMES,
    "muwaqqit_base_url": MUWAQQIT_BASE_URL_FOR_DESC
}
for key, value in critical_configs.items():
    if value is None:
        print(f"FATAL: Critical configuration key '{key}' is missing in config.json. Exiting.")
        sys.exit(1)
if not isinstance(DAYS_TO_PROCESS_IN_ADVANCE, int) or DAYS_TO_PROCESS_IN_ADVANCE < 1:
    print(f"FATAL: 'processing_days_in_advance' must be an integer >= 1. Found: {DAYS_TO_PROCESS_IN_ADVANCE}. Exiting.")
    sys.exit(1)

def get_current_device_location():
    """
    Fetches the current public IP and geolocates it to get latitude, longitude, and timezone.
    Returns (ip, latitude, longitude, timezone) or (None, None, None, None) on failure.
    """
    print("Attempting to get current device location via IP geolocation...")
    ip = None
    try:
        # Get public IP address
        ip_response = requests.get("https://api.ipify.org?format=json", timeout=5)
        ip_response.raise_for_status()
        ip = ip_response.json().get("ip")
        print(f"Public IP address: {ip}")
    except Exception as e:
        print(f"Error getting public IP: {e}")
        return None, None, None, None

    if not ip:
        return None, None, None, None

    # Geocode IP to location
    # Using ip-api.com, which is free for non-commercial use, up to 45 requests/minute
    try:
        geo_response = requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
        geo_response.raise_for_status()
        geo_data = geo_response.json()

        if geo_data.get("status") == "success":
            latitude = geo_data.get("lat")
            longitude = geo_data.get("lon")
            timezone = geo_data.get("timezone") # e.g., "America/New_York"
            print(f"Geolocation successful: Lat={latitude}, Lon={longitude}, Timezone={timezone}")
            return ip, latitude, longitude, timezone
        else:
            print(f"IP geolocation failed for {ip}: {geo_data.get('message', 'Unknown error')}")
            return ip, None, None, None
    except Exception as e:
        print(f"Error during IP geolocation for {ip}: {e}")
        return ip, None, None, None

def get_existing_prayer_events_for_day(service, target_date_obj, target_tz):
    """
    Retrieves existing managed prayer events from the Google Calendar for a specific day.

    Args:
        service (googleapiclient.discovery.Resource): The authenticated Google Calendar API service.
        target_date_obj (datetime.date): The date object for which to fetch events.
        target_tz (pytz.timezone): The timezone object for the target date.

    Returns:
        dict: A dictionary where keys are event summaries (e.g., 'Fajr Prayer')
              and values are the Google Calendar event resource objects for
              existing managed prayer events on that day. Returns an empty dict
              if an error occurs or no events are found.
    """
    print(f"Listing existing prayer events on {target_date_obj.strftime('%Y-%m-%d')}...")
    day_start_naive = datetime.combine(target_date_obj, dt_time.min)
    day_end_naive = datetime.combine(target_date_obj, dt_time.max)
    day_start_aware = target_tz.localize(day_start_naive)
    day_end_aware = target_tz.localize(day_end_naive)

    existing_events_map = {}
    page_token = None
    while True:
        try:
            events_result = service.events().list(
                calendarId=CALENDAR_ID,
                timeMin=day_start_aware.isoformat(),
                timeMax=day_end_aware.isoformat(),
                singleEvents=True,
                orderBy='startTime',
                pageToken=page_token
            ).execute()
            events = events_result.get('items', [])

            for event in events:
                summary = event.get('summary', '')
                is_managed_prayer_event = any(f'{prayer_name} Prayer' == summary for prayer_name in MANAGED_PRAYER_NAMES)
                if is_managed_prayer_event:
                    existing_events_map[summary] = event

            page_token = events_result.get('nextPageToken')
            if not page_token:
                break
        except HttpError as e:
            print(f"API error listing events for {target_date_obj.strftime('%Y-%m-%d')}: {e}")
            return {}
        except Exception as e_list:
            print(f"Unexpected error listing events for {target_date_obj.strftime('%Y-%m-%d')}: {e_list}")
            return {}

    print(f"Found {len(existing_events_map)} managed prayer events for {target_date_obj.strftime('%Y-%m-%d')}.")
    return existing_events_map

def create_or_update_prayer_event(service, prayer_name, start_dt_aware, end_dt_aware, date_str_for_desc_url, target_tz_obj, location_data_for_description, existing_event_data=None):
    event_summary = f'{prayer_name} Prayer'

    # --- Construct dynamic description URL ---
    # MUWAQQIT_BASE_URL_FOR_DESC should be the clean base URL from config
    # (the one without any location parameters, same as used by scraper)
    
    # Load the clean base URL, as MUWAQQIT_BASE_URL_FOR_DESC might be the old full one if not updated
    # Best to rely on the already cleaned BASE_URL from config used by scraper for consistency
    # For simplicity here, we'll assume MUWAQQIT_BASE_URL_FOR_DESC is the cleaned one.
    # If not, you should use config.get('muwaqqit_base_url') here too.
    
    base_desc_url = config.get('muwaqqit_base_url') # Use the cleaned base URL
    
    url_params_desc = []
    loc_display_name = "configured location" # Fallback display name

    if location_data_for_description:
        loc_tz = location_data_for_description.get("timezone", target_tz_obj.zone) # Fallback to event's timezone
        if "latitude" in location_data_for_description and "longitude" in location_data_for_description:
            lat = location_data_for_description["latitude"]
            lon = location_data_for_description["longitude"]
            url_params_desc.append(f"lt={lat}")
            url_params_desc.append(f"ln={lon}")
            url_params_desc.append(f"tz={urllib.parse.quote_plus(loc_tz)}")
            loc_display_name = f"Lat {lat}, Lon {lon}"
        elif "address" in location_data_for_description:
            address = location_data_for_description["address"]
            url_params_desc.append(f"add={urllib.parse.quote_plus(address)}")
            url_params_desc.append(f"tz={urllib.parse.quote_plus(loc_tz)}")
            loc_display_name = address
        # If neither, it will just be the base_desc_url + date
    
    url_params_desc.append(f"d={date_str_for_desc_url}")
    dynamic_muwaqqit_url = f"{base_desc_url}&{'&'.join(url_params_desc)}"
    # --- End of dynamic URL construction ---

    event_description = (
        f"Time for {prayer_name} prayer.\n"
        f"Prayer times calculated for location: {loc_display_name} (Timezone: {loc_tz})\n"
        f"URL for this day's times: {dynamic_muwaqqit_url}"
    )

    event_body = {
        'summary': event_summary,
        'start': {'dateTime': start_dt_aware.isoformat(), 'timeZone': target_tz_obj.zone},
        'end': {'dateTime': end_dt_aware.isoformat(), 'timeZone': target_tz_obj.zone},
        'reminders': {
            'useDefault': False,
            'overrides': [{'method': 'popup', 'minutes': EVENT_REMINDER_MINUTES}],
        },
        'description': event_description,
    }

    if existing_event_data:
        try:
            existing_start_str = existing_event_data.get('start', {}).get('dateTime')
            existing_end_str = existing_event_data.get('end', {}).get('dateTime')
            existing_start_dt = datetime.fromisoformat(existing_start_str).astimezone(target_tz_obj)
            existing_end_dt = datetime.fromisoformat(existing_end_str).astimezone(target_tz_obj)
            needs_update = (
                existing_start_dt != start_dt_aware or
                existing_end_dt != end_dt_aware or
                existing_event_data.get('description') != event_description # Also check if description changed
            )
        except Exception as e_comp:
            print(f"Error comparing event data for {event_summary} on {date_str_for_desc_url}, forcing update: {e_comp}")
            needs_update = True

        if needs_update:
            try:
                print(f"Updating event for {prayer_name} on {date_str_for_desc_url}...")
                updated_event = service.events().update(
                    calendarId=CALENDAR_ID, eventId=existing_event_data['id'], body=event_body).execute()
                print(f"Event updated for {prayer_name}: {updated_event.get('htmlLink')}")
            except HttpError as e:
                print(f"API error updating event for {prayer_name} on {date_str_for_desc_url}: {e}")
            except Exception as e_upd:
                print(f"Unexpected error updating event for {prayer_name} on {date_str_for_desc_url}: {e_upd}")
        else:
            print(f"Event for {prayer_name} on {date_str_for_desc_url} is already up-to-date. No action taken.")
    else:
        try:
            print(f"Creating new event for {prayer_name} on {date_str_for_desc_url}...")
            created_event = service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
            print(f"Event created for {prayer_name}: {created_event.get('htmlLink')}")
        except HttpError as e:
            print(f"API error creating event for {prayer_name} on {date_str_for_desc_url}: {e}")
        except Exception as e_crt:
            print(f"Unexpected error creating event for {prayer_name} on {date_str_for_desc_url}: {e_crt}")

def main():
    print("Starting Prayer Calendar Manager...")
    gcal_service = None

    current_app_config = load_config()
    global LOCATION_CHECK_ENABLED, LOCATION_THRESHOLD_KM
    global LAST_CHECKED_IP, LAST_CHECKED_LATITUDE, LAST_CHECKED_LONGITUDE, LAST_CHECKED_TIMEZONE
    global USER_LOCATION_ADDRESS_FALLBACK, TARGET_TIMEZONE_STR

    LOCATION_CHECK_ENABLED = current_app_config.get('location_check_enabled', False)
    LOCATION_THRESHOLD_KM = current_app_config.get('location_threshold_km', 20.0)
    LAST_CHECKED_IP = current_app_config.get('last_checked_ip')
    LAST_CHECKED_LATITUDE = current_app_config.get('last_checked_latitude')
    LAST_CHECKED_LONGITUDE = current_app_config.get('last_checked_longitude')
    LAST_CHECKED_TIMEZONE = current_app_config.get('last_checked_timezone')
    USER_LOCATION_ADDRESS_FALLBACK = current_app_config.get('user_location_address')
    TARGET_TIMEZONE_STR = current_app_config.get('target_timezone')

    try:
        current_ip = None
        current_latitude = None
        current_longitude = None
        current_timezone = None
        location_changed_or_first_run = False # Flag to track if location data in config needs update
        location_data_for_scraper = {}

        if LOCATION_CHECK_ENABLED:
            current_ip, current_latitude, current_longitude, current_timezone = get_current_device_location()

            if current_ip is None or current_latitude is None or current_longitude is None or current_timezone is None:
                print("Could not determine current location accurately via IP geolocation.")
                if LAST_CHECKED_LATITUDE is not None and LAST_CHECKED_LONGITUDE is not None and LAST_CHECKED_TIMEZONE is not None:
                    print("Using last known location for this run.")
                    location_data_for_scraper = {
                        "latitude": LAST_CHECKED_LATITUDE, "longitude": LAST_CHECKED_LONGITUDE,
                        "timezone": LAST_CHECKED_TIMEZONE,
                        "address_for_display": f"Last Known: Lat {LAST_CHECKED_LATITUDE}, Lon {LAST_CHECKED_LONGITUDE}"
                    }
                    # Location itself didn't change from what's stored, but IP geo failed.
                    # We don't mark location_changed_or_first_run = True, so config won't be re-saved with null IP.
                else:
                    print("No last known location. Using configured user_location_address and target_timezone.")
                    location_data_for_scraper = {
                        "address": USER_LOCATION_ADDRESS_FALLBACK, "timezone": TARGET_TIMEZONE_STR,
                        "address_for_display": USER_LOCATION_ADDRESS_FALLBACK
                    }
                    location_changed_or_first_run = True # Treat as first run for this address to save its details if successful
            elif LAST_CHECKED_LATITUDE is not None and LAST_CHECKED_LONGITUDE is not None and LAST_CHECKED_TIMEZONE is not None:
                old_coords = (LAST_CHECKED_LATITUDE, LAST_CHECKED_LONGITUDE)
                new_coords = (current_latitude, current_longitude)
                distance_km = geodesic(old_coords, new_coords).km
                print(f"Distance from last known location: {distance_km:.2f} km.")

                if distance_km >= LOCATION_THRESHOLD_KM or current_timezone != LAST_CHECKED_TIMEZONE:
                    print(f"Significant location change detected (Distance: {distance_km:.2f}km, Threshold: {LOCATION_THRESHOLD_KM}km or TZ changed: {LAST_CHECKED_TIMEZONE} -> {current_timezone}).")
                    location_changed_or_first_run = True
                    location_data_for_scraper = {
                        "latitude": current_latitude, "longitude": current_longitude,
                        "timezone": current_timezone,
                        "address_for_display": f"Current IP Location: Lat {current_latitude}, Lon {current_longitude}"
                    }
                else:
                    print(f"Location and timezone are within threshold. Using last known location data.")
                    location_data_for_scraper = { # Use the last known (which is same as current)
                        "latitude": LAST_CHECKED_LATITUDE, "longitude": LAST_CHECKED_LONGITUDE,
                        "timezone": LAST_CHECKED_TIMEZONE,
                        "address_for_display": f"Last Known (Stable): Lat {LAST_CHECKED_LATITUDE}, Lon {LAST_CHECKED_LONGITUDE}"
                    }
            else: # First run with successful IP geolocation
                print("First run with IP geolocation. Using current IP-based location.")
                location_changed_or_first_run = True
                location_data_for_scraper = {
                    "latitude": current_latitude, "longitude": current_longitude,
                    "timezone": current_timezone,
                    "address_for_display": f"Current IP Location: Lat {current_latitude}, Lon {current_longitude}"
                }
            
            if location_changed_or_first_run and current_latitude is not None: # Only save if we got valid current geo data and it's a change/first run
                updated_config = load_config()
                updated_config['last_checked_ip'] = current_ip
                updated_config['last_checked_latitude'] = current_latitude
                updated_config['last_checked_longitude'] = current_longitude
                updated_config['last_checked_timezone'] = current_timezone
                save_config(updated_config)
                print("Updated last known location in config.json with current IP-based location.")
        
        else: # Location check is disabled
            print("Location check disabled. Using configured user_location_address and target_timezone.")
            location_data_for_scraper = {
                "address": USER_LOCATION_ADDRESS_FALLBACK,
                "timezone": TARGET_TIMEZONE_STR,
                "address_for_display": USER_LOCATION_ADDRESS_FALLBACK
            }

        # Now, always proceed with the main logic using location_data_for_scraper
        # The 'should_proceed_with_update' flag is removed from this top level.
        # The script will always attempt to update the X-day window.

        effective_timezone_for_ops = location_data_for_scraper.get("timezone", TARGET_TIMEZONE_STR)
        print(f"Using effective timezone for operations: {effective_timezone_for_ops}")
        target_tz = pytz.timezone(effective_timezone_for_ops)

        gcal_service = authenticate_google_calendar()
        if not gcal_service:
            print("Failed to authenticate with Google Calendar. Exiting.")
            sys.exit(1)

        for i in range(DAYS_TO_PROCESS_IN_ADVANCE):
            # It will use the `location_data_for_scraper` and `target_tz` determined above.
            current_processing_date = (datetime.now(target_tz) + timedelta(days=i)).date()
            current_processing_date_str = current_processing_date.strftime('%Y-%m-%d')
            print(f"\n--- Processing for date: {current_processing_date_str} ---")
            existing_events_on_this_day = get_existing_prayer_events_for_day(gcal_service, current_processing_date, target_tz)
            print(f"Scraping prayer times for {current_processing_date_str} for location: {location_data_for_scraper.get('address_for_display', 'N/A')}")
            
            prayer_schedule_for_this_day = get_prayer_times_with_ends(
                target_date_obj_override=current_processing_date,
                location_params=location_data_for_scraper
            )

            if prayer_schedule_for_this_day is None:
                print(f"Scraping for {current_processing_date_str} was interrupted or failed. Aborting further processing.")
                sys.exit(1)
            if not prayer_schedule_for_this_day:
                print(f"Failed to scrape prayer times for {current_processing_date_str}. Skipping this day.")
                continue

            print(f"\nPrayer Schedule to Process for {current_processing_date_str}:")
            for p, t_info in prayer_schedule_for_this_day.items():
                 print(f"  {p}: Start: {t_info.get('start')} on {t_info.get('date_for_start')}, End: {t_info.get('end')} on {t_info.get('date_for_end')}")

            print(f"\nProcessing and creating/updating Google Calendar events for {current_processing_date_str}...")
            for prayer_name, times_info in prayer_schedule_for_this_day.items():
                start_time_str = times_info.get('start')
                end_time_str = times_info.get('end')
                start_date_str = times_info.get('date_for_start')
                end_date_str = times_info.get('date_for_end')

                if not all([start_time_str, end_time_str, start_date_str, end_date_str]):
                    print(f"Skipping {prayer_name} for {current_processing_date_str} due to missing time/date information.")
                    continue
                try:
                    start_datetime_naive = datetime.strptime(f"{start_date_str} {start_time_str}", "%Y-%m-%d %H:%M:%S")
                    end_datetime_naive = datetime.strptime(f"{end_date_str} {end_time_str}", "%Y-%m-%d %H:%M:%S")
                    start_datetime_aware = target_tz.localize(start_datetime_naive)
                    end_datetime_aware = target_tz.localize(end_datetime_naive)
                    if end_datetime_aware <= start_datetime_aware:
                        print(f"Warning: End time for {prayer_name} ({end_datetime_aware}) on {start_date_str} is not after start time ({start_datetime_aware}). Skipping.")
                        continue
                    event_summary_key = f'{prayer_name} Prayer'
                    existing_event_to_update = existing_events_on_this_day.get(event_summary_key)
                    create_or_update_prayer_event(
                        gcal_service,
                        prayer_name,
                        start_datetime_aware,
                        end_datetime_aware,
                        start_date_str,
                        target_tz,
                        location_data_for_scraper,
                        existing_event_data=existing_event_to_update
                    )

                except ValueError as ve:
                    print(f"Error parsing date/time for {prayer_name} on {current_processing_date_str}: {ve}.")
                except Exception as e:
                    print(f"An unexpected error occurred while processing {prayer_name} on {current_processing_date_str}: {e}")

    except KeyboardInterrupt:
        print("\nProcess interrupted by user (Ctrl+C). Exiting gracefully.")
        sys.exit(0)
    except Exception as e:
        print(f"\nAn unexpected error occurred in the main process: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\nPrayer Calendar Manager finished all processing days.")
    sys.exit(0)

if __name__ == '__main__':
    main()

# --- END OF FILE prayer_calendar_manager.py ---
# --- START OF FILE prayer_calendar_manager.py ---

from google_calendar_setup import authenticate_google_calendar, HttpError
from scrape_prayer_times import get_prayer_times_with_ends # This will be called for each day
from datetime import datetime, timedelta, time as dt_time
import pytz
from config_loader import load_config
import sys # For sys.exit

# Load configuration
try:
    config = load_config()
except Exception as e:
    print(f"FATAL: Could not load configuration for Calendar Manager: {e}")
    sys.exit(1)

# Use values from config or provide defaults/raise errors for critical ones
CALENDAR_ID = config.get('calendar_id')
EVENT_REMINDER_MINUTES = config.get('event_reminder_minutes', 0)
TARGET_TIMEZONE_STR = config.get('target_timezone')
MANAGED_PRAYER_NAMES = config.get('managed_prayer_names')
MUWAQQIT_BASE_URL_FOR_DESC = config.get('muwaqqit_base_url')
# THIS IS THE KEY FOR N-DAY PROCESSING
DAYS_TO_PROCESS_IN_ADVANCE = config.get('processing_days_in_advance', 1) # Default to 1 if not in config

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


def get_existing_prayer_events_for_day(service, target_date_obj, target_tz):
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

def create_or_update_prayer_event(service, prayer_name, start_dt_aware, end_dt_aware, date_str_for_desc_url, existing_event_data=None):
    event_summary = f'{prayer_name} Prayer'
    event_description = f"Time for {prayer_name} prayer.\nURL for this day's times: {MUWAQQIT_BASE_URL_FOR_DESC}&d={date_str_for_desc_url}"

    event_body = {
        'summary': event_summary,
        'start': {'dateTime': start_dt_aware.isoformat(), 'timeZone': TARGET_TIMEZONE_STR},
        'end': {'dateTime': end_dt_aware.isoformat(), 'timeZone': TARGET_TIMEZONE_STR},
        'reminders': {
            'useDefault': False,
            'overrides': [{'method': 'popup', 'minutes': EVENT_REMINDER_MINUTES}],
        },
        'description': event_description,
    }

    target_tz_for_comparison = pytz.timezone(TARGET_TIMEZONE_STR) # Define for comparison

    if existing_event_data:
        try:
            existing_start_str = existing_event_data.get('start', {}).get('dateTime')
            existing_end_str = existing_event_data.get('end', {}).get('dateTime')
            
            existing_start_dt = datetime.fromisoformat(existing_start_str).astimezone(target_tz_for_comparison)
            existing_end_dt = datetime.fromisoformat(existing_end_str).astimezone(target_tz_for_comparison)

            needs_update = (
                existing_start_dt != start_dt_aware or
                existing_end_dt != end_dt_aware
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
    gcal_service = authenticate_google_calendar()
    if not gcal_service:
        print("Failed to authenticate with Google Calendar. Exiting.")
        return

    target_tz = pytz.timezone(TARGET_TIMEZONE_STR)
    
    # --- LOOP FOR N DAYS ---
    for i in range(DAYS_TO_PROCESS_IN_ADVANCE):
        # Determine the specific date for this iteration
        current_processing_date = (datetime.now(target_tz) + timedelta(days=i)).date()
        current_processing_date_str = current_processing_date.strftime('%Y-%m-%d')
        
        print(f"\n--- Processing for date: {current_processing_date_str} ---")

        # 1. Get existing events for this specific day
        existing_events_on_this_day = get_existing_prayer_events_for_day(gcal_service, current_processing_date, target_tz)

        # 2. Scrape Prayer Times for this specific day
        print(f"Scraping prayer times for {current_processing_date_str}...")
        # Pass the specific date to the scraper
        prayer_schedule_for_this_day = get_prayer_times_with_ends(target_date_obj_override=current_processing_date)
        
        if not prayer_schedule_for_this_day:
            print(f"Failed to scrape prayer times for {current_processing_date_str}. Skipping this day.")
            continue # Move to the next day in the loop

        print(f"\nPrayer Schedule to Process for {current_processing_date_str}:")
        for p, t in prayer_schedule_for_this_day.items():
             print(f"  {p}: Start: {t.get('start')} on {t.get('date_for_start')}, End: {t.get('end')} on {t.get('date_for_end')}")

        # 3. Process and Create/Update Events for this specific day
        print(f"\nProcessing and creating/updating Google Calendar events for {current_processing_date_str}...")
        for prayer_name, times_info in prayer_schedule_for_this_day.items():
            start_time_str = times_info.get('start')
            end_time_str = times_info.get('end')
            # These dates should come correctly from the scraper for the current_processing_date
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
                    start_date_str, # Date for description URL (should be same as current_processing_date_str or one day after for Isha end)
                    existing_event_data=existing_event_to_update
                )

            except ValueError as ve:
                print(f"Error parsing date/time for {prayer_name} on {current_processing_date_str}: {ve}.")
            except Exception as e:
                print(f"An unexpected error occurred while processing {prayer_name} on {current_processing_date_str}: {e}")

    print("\nPrayer Calendar Manager finished all processing days.")

if __name__ == '__main__':
    main()

# --- END OF FILE prayer_calendar_manager.py ---
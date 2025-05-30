# Hanafi Prayer Time Google Calendar Integration App

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Selenium](https://img.shields.io/badge/Selenium-43B02A?style=for-the-badge&logo=selenium&logoColor=white)
![Google Calendar API](https://img.shields.io/badge/Google%20Calendar%20API-4285F4?style=for-the-badge&logo=google-calendar&logoColor=white)

A Python application designed to automate the process of fetching daily prayer times based on Hanafi standards from a specified website and seamlessly integrating them into a user's Google Calendar. This ensures that prayer times are always up-to-date and accessible in your personal schedule, with intelligent location awareness.

## Table of Contents
- [Features](#features)
- [How It Works](#how-it-works)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Google API Setup](#google-api-setup)
  - [Configuration](#configuration)
  - [Running the Application](#running-the-application)
- [Project Structure](#project-structure)
- [Future Enhancements](#future-enhancements)
- [License](#license)
- [Contact](#contact)

## Features

*   **Automated Prayer Time Scraping:** Automatically fetches daily prayer times (Fajr, Zuhr, Asr, Maghrib, Isha) from a configurable online source (`muwaqqit.com`).
*   **Dynamic IP-Based Location Awareness:**
    *   Optionally checks the device's current public IP-based geolocation on each run.
    *   Compares current location with the last known location.
    *   Prayer times are fetched for the **current IP-based location** if it has significantly changed (beyond a configurable distance or timezone change) or on the first run.
    *   If the location has not significantly changed, prayer times are fetched for the **last known stable location** to ensure the calendar's X-day buffer is always maintained.
    *   Stores the last successfully processed IP-based location to minimize redundant calculations and API calls.
*   **Hanafi Standard Adherence:** Specifically designed to extract times based on Hanafi calculation methods as interpreted from `muwaqqit.com`'s parameters.
*   **Google Calendar Integration:** Creates and updates prayer events directly in your Google Calendar.
*   **Duplicate Prevention & Updates:** Intelligently checks for existing events to avoid duplicates and updates event times and descriptions if they change.
*   **Configurable Processing Window:** Processes prayer times for multiple days in advance (e.g., the next 7 days) to keep your calendar proactive.
*   **Customizable Timeouts:** Allows configuration of page load and overall process timeouts for robust web scraping.
*   **Robust Error Handling & Graceful Shutdown:** Includes robust error handling for network issues, website changes, API errors (saving page source on scraper errors for debugging), and provides clean, user-friendly exit messages when the application is interrupted (e.g., via Ctrl+C).
*   **Headless Browser Support:** Runs Selenium in headless mode by default, meaning no browser window will pop up during execution.

## How It Works

The application operates in a sequence of steps:

1.  **Configuration Loading:** Reads all necessary settings from `config.json`, including Google Calendar details, `muwaqqit.com` parameters, location preferences, and last known location data.
2.  **(Optional) IP-Based Geolocation Check:**
    *   If `location_check_enabled` is true, fetches the device's current public IP address.
    *   Uses an external geolocation service (`ip-api.com`) to determine current latitude, longitude, and timezone.
    *   Compares this current location with the `last_checked_latitude`, `last_checked_longitude`, and `last_checked_timezone` stored in `config.json`.
    *   Determines if a significant location change has occurred based on a configurable distance threshold (`location_threshold_km`) or a timezone change.
3.  **Determine Location for Prayer Time Calculation:**
    *   If a significant location change is detected (or it's the first run with location checking enabled), the current IP-based location is used.
    *   If no significant change, the last successfully processed location is used.
    *   If location checking is disabled, a user-defined `user_location_address` from `config.json` is used.
4.  **Google Calendar Authentication:** Authenticates with the Google Calendar API.
5.  **Daily Processing Loop:** Iterates through a specified number of upcoming days (`processing_days_in_advance`).
    *   **Existing Event Check:** Queries Google Calendar for any existing prayer events for the current day being processed.
    *   **Web Scraping:** Uses Selenium to visit `muwaqqit.com`. The URL is dynamically constructed using the determined location (either IP-based coordinates or the fallback address) and the specific date. It extracts the start and end times for each prayer.
    *   **Calendar Synchronization:** Compares the scraped times with existing calendar events. It creates new events or updates existing ones (including the event description which contains a link to `muwaqqit.com` for the specific location and date).
6.  **Update Last Known Location:** If a new IP-based location was used for processing, its details (`ip`, `latitude`, `longitude`, `timezone`) are saved back to `config.json`.
7.  **Completion:** The process repeats for all specified days, ensuring your calendar is synchronized. The script exits gracefully, handling errors and user interruptions.

## Getting Started

Follow these instructions to get a copy of the project up and running on your local machine.

### Prerequisites

*   **Python 3.x:** Ensure you have Python installed. You can download it from [python.org](https://www.python.org/downloads/).
*   **Git:** For cloning the repository. Download from [git-scm.com](https://git-scm.com/downloads).
*   **Google Account:** A Google account with Google Calendar enabled to manage events.
*   **Google Chrome or Brave Browser:** The application uses Selenium to automate a web browser. You'll need either Google Chrome or Brave Browser installed. The appropriate ChromeDriver is automatically managed by `webdriver-manager`. If using Brave, its executable path must be configured in `config.json`.
*   **Internet Connection:** Required for IP geolocation, fetching prayer times, and Google Calendar API communication.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/SonicZak/Hanafi-Prayer-Time-App.git
    cd Hanafi-Prayer-Time-App
    ```

2.  **Create and activate a Python virtual environment (highly recommended):**
    ```bash
    python -m venv venv
    ```
    *   **On Windows:**
        ```bash
        .\venv\Scripts\activate
        ```
        *(If you encounter a script execution error on Windows PowerShell, run `Set-ExecutionPolicy RemoteSigned` in an Administrator PowerShell window, confirm with `Y`, then try activating again.)*
    *   **On macOS/Linux:**
        ```bash
        source venv/bin/activate
        ```

3.  **Install the required Python packages:**
    ```bash
    pip install -r requirements.txt
    ```
    *(This will install `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`, `selenium`, `webdriver-manager`, `pytz`, `requests`, and `geopy`.)*

### Google API Setup (only for Developers/Contributers)

This project uses the Google Calendar API. You need to enable the API and download your credentials:

1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  Create a new project or select an existing one.
3.  Navigate to "APIs & Services" > "Enabled APIs & Services".
4.  Search for and enable the "Google Calendar API".
5.  Go to "APIs & Services" > "Credentials".
6.  Click "Create Credentials" > "OAuth client ID".
7.  Select "Desktop app" as the application type and give it a name (e.g., "PrayerApp").
8.  Click "Create", then click "Download JSON" on the next screen.
9.  Rename the downloaded file to `credentials.json` and place it in your project's root directory. **Do NOT share this file publicly or commit it to your GitHub repository.** (It's already in `.gitignore`).
10. The first time you run the app, it will open a browser window asking you to authenticate with your Google account. After successful authentication, `token.json` will be automatically generated and saved in your project's root directory. **This file also contains sensitive user data and should NOT be shared or committed.**

### Configuration

Open the `config.json` file in your project's root directory and modify the settings as needed:

*   `"brave_path"`: (Optional) If you use Brave browser, provide the full path to its executable (e.g., `C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe`). If left blank or invalid, the app will attempt to use a generic ChromeDriver installation via `webdriver-manager` for Chrome.
*   `"calendar_id"`: Your Google Calendar ID. You can find this in Google Calendar settings under "Integrate calendar" for the specific calendar you want to use.
*   `"target_timezone"`: **Fallback timezone** if IP geolocation fails and no last known timezone is available (e.g., `"Australia/Sydney"`). The script primarily uses the timezone detected via IP geolocation or the last successfully used timezone.
*   `"event_reminder_minutes"`: Number of minutes before the event to trigger a popup reminder (e.g., `5`).
*   `"user_location_address"`: A human-readable address (e.g., `"1 Main St, Anytown, USA"`). This is used as a **fallback** if IP geolocation fails and no prior location data exists, or if `location_check_enabled` is false. It's also used for display purposes.
*   `"location_check_enabled"`: Set to `true` to enable dynamic IP-based location checking, or `false` to always use `user_location_address`.
*   `"location_threshold_km"`: The distance in kilometers (e.g., `20.0`). If the device moves further than this from the last known location, prayer times will be updated for the new location.
*   `"last_checked_ip"`: (Managed by the script) Stores the last IP address for which location was successfully processed. Initialize to `null`.
*   `"last_checked_latitude"`: (Managed by the script) Stores the last latitude. Initialize to `null`.
*   `"last_checked_longitude"`: (Managed by the script) Stores the last longitude. Initialize to `null`.
*   `"last_checked_timezone"`: (Managed by the script) Stores the last timezone string. Initialize to `null`.
*   `"muwaqqit_base_url"`: The base URL for `muwaqqit.com` containing **only calculation parameters** (like solar angles, refraction coefficient, etc.), and **NO location parameters** (like `add=`, `lt=`, `ln=`, `tz=`). The script adds location parameters dynamically. Example: `"https://www.muwaqqit.com/index?diptype=apparent&ea=-19.0&fa=-19.0..."`
*   `"prayer_definitions"`: Defines the text labels the scraper looks for on the website for each prayer's start and end times.
*   `"managed_prayer_names"`: A list of prayer names the manager should specifically track and update.
*   `"processing_days_in_advance"`: The number of upcoming days (including today) for which the app should fetch and update prayer times (e.g., `7` for a week).
*   `"timeouts"`: Various timeout settings for the web scraping process.
*   `"google_auth"`: (Generally leave as default) Paths for `token.json` and `credentials.json`, Google API scopes, and redirect URI for OAuth.

### Running the Application

Once everything is set up, run the main script from your activated virtual environment in the terminal:

```bash
python prayer_calendar_manager.py
```

The application will then proceed to check location (if enabled), authenticate, scrape prayer times, and update your Google Calendar. You can schedule this script to run periodically (e.g., hourly or daily) using tools like Windows Task Scheduler or cron jobs on Linux/macOS.

## Project Structure

```bash
.
├── __pycache__/                # Python bytecode (ignored by Git)
├── config.json                 # Application configuration settings
├── config_loader.py            # Utility to load/save configuration from config.json
├── credentials.json            # Google API client secrets (sensitive, ignored by Git)
├── google_calendar_setup.py    # Handles Google Calendar API authentication
├── prayer_calendar_manager.py  # Main script: orchestrates scraping and calendar updates
├── requirements.txt            # List of Python dependencies
├── scrape_prayer_times.py      # Contains logic for web scraping prayer times
├── token.json                  # Google OAuth token (sensitive, ignored by Git)
├── run_prayer_app.bat          # Example batch file for Windows Task Scheduler
├── run_log.txt                 # Log file generated by run_script.bat (ignored by Git)
└── LICENSE                     # MIT License file
```


## Future Enhancements (Ideas for continued development)

*   **Structured Logging:** Implement Python's `logging` module for more detailed, categorized, and configurable output to files or console (beyond the current batch file redirection), making debugging and monitoring easier.
*   **Retry Logic for Scraping:** Enhance web scraping with retry mechanisms (e.g., using the `tenacity` library) for transient network errors or temporary website unresponsiveness from `muwaqqit.com`.
*   **Command Line Arguments:** Add command-line arguments for more flexible execution, such as:
    *   Forcing an update regardless of location change (`--force-update`).
    *   Specifying a temporary location for a single run without altering `config.json`.
    *   Overriding `processing_days_in_advance` for a specific run.
*   **Alternative Geolocation Methods:**
    *   Allow manual input of latitude/longitude in `config.json` as an alternative to IP-based geolocation if the user prefers or if IP geolocation is unreliable for them.
    *   Option to use different IP geolocation APIs if `ip-api.com` becomes unsuitable.
*   **More Granular Configuration for `muwaqqit.com`:** Expose more of `muwaqqit.com`'s calculation parameters (like elevation, specific twilight angles if desired beyond defaults) in `config.json` for advanced users.
*   **Graphical User Interface (GUI):** Develop a simple desktop or web-based GUI for easier configuration and manual triggering of the script.
*   **Unit/Integration Tests:** Implement automated tests to ensure the reliability of core components like location checking, date calculations, API interactions, and scraping logic, especially if further features are added.
*   **Multi-user Support (Major):** If the application were to be used by others, implement user accounts and manage separate Google Calendar credentials and configurations.
*   **Alternative Prayer Time Sources/Calculation Methods (Major):** Allow users to choose from different online prayer time sources or input their location for direct calculation using established astronomical libraries.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

*   **GitHub:** [SonicZak](https://github.com/SonicZak)
*   **LinkedIn:** [www.linkedin.com/in/zakisheikh1](www.linkedin.com/in/zakisheikh1)
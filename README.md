# Hanafi Prayer Time Google Calendar Integration App

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Selenium](https://img.shields.io/badge/Selenium-43B02A?style=for-the-badge&logo=selenium&logoColor=white)
![Google Calendar API](https://img.shields.io/badge/Google%20Calendar%20API-4285F4?style=for-the-badge&logo=google-calendar&logoColor=white)

A Python application designed to automate the process of fetching daily prayer times based on Hanafi standards from a specified website and seamlessly integrating them into a user's Google Calendar. This ensures that prayer times are always up-to-date and accessible in your personal schedule.

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
*   **Hanafi Standard Adherence:** Specifically designed to extract times based on Hanafi calculation methods.
*   **Google Calendar Integration:** Creates and updates prayer events directly in your Google Calendar.
*   **Duplicate Prevention & Updates:** Intelligently checks for existing events to avoid duplicates and updates event times if they change (e.g., due to daylight saving adjustments).
*   **Configurable Processing Window:** Processes prayer times for multiple days in advance (e.g., the next 7 days) to keep your calendar proactive.
*   **Customizable Timeouts:** Allows configuration of page load and overall process timeouts for robust web scraping.
*   **Error Handling:** Includes robust error handling for network issues, website changes, and API errors, saving page source on scraper errors for debugging.
*   **Headless Browser Support:** Runs Selenium in headless mode by default, meaning no browser window will pop up during execution.

## How It Works

The application operates in a sequence of steps:

1.  **Configuration Loading:** Reads all necessary settings (calendar ID, target timezone, website URL, prayer definitions, API paths, etc.) from `config.json`.
2.  **Google Calendar Authentication:** Authenticates with the Google Calendar API, either by refreshing an existing token or by guiding the user through an OAuth 2.0 flow via their web browser to obtain new credentials.
3.  **Daily Processing Loop:** Iterates through a specified number of upcoming days.
    *   **Existing Event Check:** Queries the Google Calendar for any already existing prayer events for the current day being processed.
    *   **Web Scraping:** Uses Selenium to visit the configured prayer time website for the specific date. It extracts the start and end times for each prayer, handling potential date offsets (e.g., if a prayer's end time falls on the next day).
    *   **Calendar Synchronization:** Compares the scraped times with existing calendar events. It creates new events if none exist or updates existing ones if the times have changed.
4.  **Completion:** The process repeats for all specified days, ensuring your calendar is synchronized.

## Getting Started

Follow these instructions to get a copy of the project up and running on your local machine.

### Prerequisites

*   **Python 3.x:** Ensure you have Python installed. You can download it from [python.org](https://www.python.org/downloads/).
*   **Git:** For cloning the repository. Download from [git-scm.com](https://git-scm.com/downloads).
*   **Google Account:** A Google account with Google Calendar enabled to manage events.
*   **Google Chrome or Brave Browser:** The application uses Selenium to automate a web browser. You'll need either Google Chrome or Brave Browser installed. If using Brave, its executable path must be configured.

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

### Google API Setup

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
*   `"target_timezone"`: The timezone for your prayer times (e.g., `"Australia/Sydney"`).
*   `"event_reminder_minutes"`: Number of minutes before the event to trigger a popup reminder (e.g., `5`).
*   `"muwaqqit_base_url"`: The base URL for the Muwaqqit website or similar. Ensure it's correctly formatted to allow appending date parameters.
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

The application will then proceed to authenticate, scrape prayer times, and update your Google Calendar. You can schedule this script to run periodically (e.g., daily) using tools like Windows Task Scheduler or cron jobs on Linux/macOS.

## Project Structure

```bash
.
├── __pycache__/                # Python bytecode (ignored by Git)
├── chromedriver-win64/         # ChromeDriver executable (ignored by Git, managed by webdriver-manager)
├── config.json                 # Application configuration settings
├── config_loader.py            # Utility to load configuration from config.json
├── credentials.json            # Google API client secrets (sensitive, ignored by Git)
├── google_calendar_setup.py    # Handles Google Calendar API authentication
├── prayer_calendar_manager.py  # Main script: orchestrates scraping and calendar updates
├── requirements.txt            # List of Python dependencies
├── scrape_prayer_times.py      # Contains logic for web scraping prayer times
├── token.json                  # Google OAuth token (sensitive, ignored by Git)
└── LICENSE                     # MIT License file
```


## Future Enhancements (Ideas for continued development)

*   **Multi-user Support:** Implement user accounts and manage separate Google Calendar credentials and configurations for each user.
*   **Graphical User Interface (GUI):** Develop a desktop or web-based GUI for easier interaction and setup.
*   **Alternative Prayer Time Sources/Calculation Methods:** Allow users to choose from different online sources or input their location for direct calculation.
*   **Improved Error Reporting:** Implement logging to a file or integrate with monitoring services for more robust error tracking.
*   **Command Line Arguments:** Add command-line arguments for easier ad-hoc execution or overrides without editing `config.json`.
*   **Unit/Integration Tests:** Add automated tests to ensure reliability of scraping and API interactions.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

*   **GitHub:** [SonicZak](https://github.com/SonicZak)
*   **LinkedIn:** [www.linkedin.com/in/zakisheikh1](www.linkedin.com/in/zakisheikh1)

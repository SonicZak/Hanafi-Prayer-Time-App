# --- START OF FILE config_loader.py ---

import json
import os

CONFIG_FILE_PATH = 'config.json'

def load_config():
    """Loads configuration from config.json."""
    if not os.path.exists(CONFIG_FILE_PATH):
        raise FileNotFoundError(f"Configuration file '{CONFIG_FILE_PATH}' not found. Please create it.")

    try:
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except json.JSONDecodeError as e:
        raise ValueError(f"Error decoding JSON from '{CONFIG_FILE_PATH}': {e}")
    except Exception as e:
        raise RuntimeError(f"Could not load configuration from '{CONFIG_FILE_PATH}': {e}")

def save_config(config_data):
    """Saves the current configuration data back to config.json."""
    try:
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4) # Use indent for pretty printing
    except Exception as e:
        print(f"Error saving configuration to '{CONFIG_FILE_PATH}': {e}")
        # Consider re-raising or handling more gracefully depending on desired behavior

if __name__ == '__main__':
    # Test loading the config
    try:
        cfg = load_config()
        print("Config loaded successfully:")
        # print(json.dumps(cfg, indent=4)) # Pretty print the whole config
        print(f"Calendar ID: {cfg.get('calendar_id')}")
        print(f"Brave Path: {cfg.get('brave_path')}")
        print(f"Prayer Definitions for Fajr Start: {cfg.get('prayer_definitions', {}).get('Fajr', {}).get('start_text')}")
        print(f"Google Auth Token Path: {cfg.get('google_auth', {}).get('token_path')}")

        # --- Test saving (optional, uncomment to run) ---
        # cfg['test_key'] = 'test_value'
        # save_config(cfg)
        # print("Test key added and config saved. Check config.json.")
        # --------------------------------------------------

    except Exception as e:
        print(f"Error in config_loader test: {e}")

# --- END OF FILE config_loader.py ---
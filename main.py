import multiprocessing
import os
import time
import logging
import json  # Added for JSON operations
import schedule
import mt5_interface1
import training1
import strategy1
import swing_trade1

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Function to import settings from settings.json
def get_project_settings(importFilepath):
    """Load project settings from a JSON file."""
    if os.path.exists(importFilepath):
        try:
            with open(importFilepath, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON: {e}")
            raise
    else:
        logging.error(f"Settings file not found: {importFilepath}")
        raise FileNotFoundError(f"Settings file not found: {importFilepath}")


def run_all_functions(module):
    """Run all callable functions within a module."""
    for name in dir(module):
        if callable(getattr(module, name)):
            logging.info(f"Running function: {name} from module {module.__name__}")
            try:
                getattr(module, name)()
            except Exception as e:
                logging.error(f"Error in function {name}: {e}")


if __name__ == "__main__":
    import_filepath = "settings.json"

    try:
        project_settings = get_project_settings(import_filepath)
        logging.info("Project settings loaded successfully.")

        # Start MT5 and check connection
        if mt5_interface1.start_mt5(
            project_settings["username"],
            project_settings["password"],
            project_settings["server"],
            project_settings["mt5Pathway"],
        ):
            logging.info("MT5 started successfully.")

            # Schedule tasks
            schedule.every().friday.at("23:30").do(lambda: run_all_functions(training1.main))
            schedule.every().hour.at(":01").do(lambda: run_all_functions(mt5_interface1.main))
            
            # Run additional modules
            run_all_functions(strategy1.main)
            run_all_functions(swing_trade1.main)

            logging.info("All modules initialized. Starting scheduled tasks.")

            # Keep the script running
            while True:
                schedule.run_pending()
                time.sleep(1)
        else:
            logging.error("Failed to start MT5. Exiting.")

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")

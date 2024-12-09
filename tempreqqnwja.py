import os
import time
import logging
import json
import schedule
import mt5_interface1
import training1
import strategy1
import swing_trade1
from multiprocessing import Process
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TensorFlow logs

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def get_project_settings(import_filepath):
    """Load project settings from a JSON file."""
    if os.path.exists(import_filepath):
        try:
            with open(import_filepath, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON: {e}")
            raise
    else:
        logging.error(f"Settings file not found: {import_filepath}")
        raise FileNotFoundError(f"Settings file not found: {import_filepath}")

def run_module_main(module_name):
    """Run the main() function of a module."""
    module = __import__(module_name)
    if hasattr(module, "main") and callable(module.main):
        try:
            logging.info(f"Running main() from module {module.__name__}")
            module.main()
        except Exception as e:
            logging.error(f"Error running main() in module {module.__name__}: {e}")

def run_all_in_parallel(module_names):
    """Run all module main() functions in parallel."""
    processes = []
    for module_name in module_names:
        process = Process(target=run_module_main, args=(module_name,))
        processes.append(process)
        process.start()

    for process in processes:
        process.join()


def run_training():
    run_module_main(training1)

def run_mt5():
    run_module_main(mt5_interface1)

def schedule_tasks():
    """Schedule tasks to run at specified times."""
    schedule.every().friday.at("23:30").do(run_training)
    schedule.every().hour.at(":01").do(run_mt5)

    while True:
        schedule.run_pending()
        time.sleep(1)


def main():
    """Main function for the script."""
    import_filepath = "settings.json"

    try:
        project_settings = get_project_settings(import_filepath)
        logging.info("Project settings loaded successfully.")

        if mt5_interface1.start_mt5(
            project_settings["username"],
            project_settings["password"],
            project_settings["server"],
            project_settings["mt5Pathway"],
        ):
            logging.info("MT5 started successfully.")

            modules = ["training1", "strategy1", "swing_trade1"]
            run_all_in_parallel(modules)

            logging.info("Modules initialized. Starting scheduled tasks.")

            # Run schedule in the main thread
            schedule_tasks()
        else:
            logging.error("Failed to start MT5. Exiting.")

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    import os
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' # Suppress TensorFlow logs
    main()

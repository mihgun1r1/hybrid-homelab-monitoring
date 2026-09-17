import os
import shutil
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

WATCH_DIR = os.getenv("WATCH_DIR", "/data/incoming")
BASE_DIR = os.getenv("BASE_DIR", "/data")

# Route files based on extensions
EXTENSION_MAP = {
    # Documents
    ".pdf": "documents",
    ".docx": "documents",
    ".xlsx": "documents",
    ".txt": "documents",
    ".csv": "documents",
    # Media
    ".png": "media",
    ".jpg": "media",
    ".jpeg": "media",
    ".mp4": "media",
    ".mkv": "media",
    # Archives & Backups
    ".zip": "archives",
    ".tar.gz": "archives",
    ".gz": "archives",
    ".iso": "backups",
    # Code / Scripts / Configs
    ".sh": "scripts",
    ".py": "scripts",
    ".yml": "scripts",
    ".yaml": "scripts",
    ".json": "scripts",
}

class AutoOrganizeHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return

        file_path = event.src_path
        filename = os.path.basename(file_path)

        # Ignore hidden/temporary system files
        if filename.startswith(".") or filename.endswith(".crdownload"):
            return

        # Small delay to ensure file write stream is completed
        time.sleep(1.5)

        ext = os.path.splitext(filename)[1].lower()
        destination_folder = EXTENSION_MAP.get(ext, "incoming")

        if destination_folder == "incoming":
            logging.info(f"Unrecognized file type for: {filename}, leaving in incoming.")
            return

        target_dir = os.path.join(BASE_DIR, destination_folder)
        os.makedirs(target_dir, exist_ok=True)
        dest_path = os.path.join(target_dir, filename)

        # Handle filename collisions
        if os.path.exists(dest_path):
            name, ext = os.path.splitext(filename)
            filename = f"{name}_{int(time.time())}{ext}"
            dest_path = os.path.join(target_dir, filename)

        try:
            shutil.move(file_path, dest_path)
            logging.info(f"Processed: {filename} -> {destination_folder}/")
        except Exception as e:
            logging.error(f"Failed to move {filename}: {e}")

if __name__ == "__main__":
    logging.info(f"Starting Storage Auto-Organizer on: {WATCH_DIR}")
    event_handler = AutoOrganizeHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIR, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
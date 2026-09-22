import os
import shutil
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WATCH_DIR = os.getenv("WATCH_DIR", "/storage/watch")
ORGANIZED_DIR = os.getenv("ORGANIZED_DIR", "/storage/organized")

CATEGORIES = {
    "Documents": [
        ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".csv", 
        ".txt", ".rtf", ".odt", ".md"
    ],
    "Images": [
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico"
    ],
    "Archives": [
        ".zip", ".tar", ".gz", ".tar.gz", ".7z", ".rar", ".bz2", ".iso", ".img"
    ],
    "Installers_and_Scripts": [
        ".deb", ".rpm", ".sh", ".bash", ".exe", ".msi", ".apk", ".bin"
    ],
    "Media": [
        ".mp4", ".mkv", ".avi", ".mov", ".mp3", ".wav", ".flac"
    ],
    "Configs_and_Logs": [
        ".json", ".yaml", ".yml", ".xml", ".log", ".conf", ".ini", ".env"
    ]
}

def get_category(filename):
    _, ext = os.path.splitext(filename.lower())
    for category, extensions in CATEGORIES.items():
        if ext in extensions:
            return category
    return "Other"

def wait_for_file_transfer(filepath, wait_seconds=1, retries=5):
    """Ensure the file has finished writing before moving it."""
    for _ in range(retries):
        try:
            initial_size = os.path.getsize(filepath)
            time.sleep(wait_seconds)
            current_size = os.path.getsize(filepath)
            if initial_size == current_size and initial_size > 0:
                return True
        except (OSError, FileNotFoundError):
            time.sleep(wait_seconds)
    return False

def get_unique_destination_path(target_folder, filename):
    base_name, ext = os.path.splitext(filename)
    dest_path = os.path.join(target_folder, filename)
    counter = 1

    while os.path.exists(dest_path):
        dest_path = os.path.join(target_folder, f"{base_name}_{counter}{ext}")
        counter += 1

    return dest_path

class FileOrganizerHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return

        source_path = event.src_path
        filename = os.path.basename(source_path)

        # Ignore hidden / temporary files (like .DS_Store, .crdownload, .tmp)
        if filename.startswith(".") or filename.endswith(".tmp") or filename.endswith(".crdownload"):
            return

        print(f"[EVENT] New file detected: {filename}", flush=True)

        if not wait_for_file_transfer(source_path):
            print(f"[SKIP] File {filename} is still busy or inaccessible.", flush=True)
            return

        category = get_category(filename)
        target_dir = os.path.join(ORGANIZED_DIR, category)
        os.makedirs(target_dir, exist_ok=True)

        destination_path = get_unique_destination_path(target_dir, filename)

        try:
            shutil.move(source_path, destination_path)
            print(f"[SUCCESS] Moved: '{filename}' -> '{category}/{os.path.basename(destination_path)}'", flush=True)
        except Exception as e:
            print(f"[ERROR] Could not move {filename}: {e}", flush=True)

if __name__ == "__main__":
    os.makedirs(WATCH_DIR, exist_ok=True)
    os.makedirs(ORGANIZED_DIR, exist_ok=True)

    print(f"[INFO] Storage organizer started.", flush=True)
    print(f"[INFO] Monitoring: {WATCH_DIR}", flush=True)
    print(f"[INFO] Target: {ORGANIZED_DIR}", flush=True)

    event_handler = FileOrganizerHandler()
    observer = Observer()
    observer.schedule(event_handler, path=WATCH_DIR, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
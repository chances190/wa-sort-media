"""WhatsApp Media Suite - GUI Application"""

import sys
import webview
from pathlib import Path

from gui.api import BackupAPI


def get_base_path():
    """Get the base path for bundled resources."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        return Path(sys._MEIPASS)

    return Path(__file__).resolve().parent.parent


def print_tree(path: Path, prefix: str = "", max_depth: int = 3, current_depth: int = 0) -> None:
    """Recursively print directory tree."""
    if current_depth >= max_depth:
        return

    try:
        items = sorted(path.iterdir())
        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            current_prefix = "└── " if is_last else "├── "
            print(f"{prefix}{current_prefix}{item.name}{'/' if item.is_dir() else ''}")

            if item.is_dir() and current_depth < max_depth - 1:
                next_prefix = prefix + ("    " if is_last else "│   ")
                print_tree(item, next_prefix, max_depth, current_depth + 1)
    except Exception as e:
        print(f"{prefix}[Error reading directory: {e}]")


def main():
    """Launch the GUI application"""
    api = BackupAPI()

    # Get the path to assets directory
    base_path = get_base_path()
    assets_dir = base_path / "gui" / "assets"

    # Debug: Print directory structure
    # print("\n=== DEBUG: Path Information ===")
    # print(f"Base path: {base_path}")
    # print(f"Assets dir: {assets_dir}")
    # print(f"Is frozen: {getattr(sys, 'frozen', False)}")

    # print(f"\nFull directory tree of {base_path}:")
    # print_tree(base_path, max_depth=4)
    # print("=== END DEBUG ===\n")

    # Create webview window pointing to HTML file
    window = webview.create_window(
        title="WhatsApp Media Suite",
        url=(assets_dir / "index.html").resolve().as_uri(),
        js_api=api,
        width=520,
        height=900,
        resizable=False,
        background_color="#ece5dd",
    )

    # Set window reference for API callbacks
    api.set_window(window)

    webview.start(debug=False)


if __name__ == "__main__":
    main()

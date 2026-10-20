"""WhatsApp Media Suite - GUI entry point."""

import webview

from gui.api import BackupAPI, get_base_path


def main() -> None:
    """Launch the GUI application."""
    api = BackupAPI()
    assets_dir = get_base_path() / "gui" / "assets"

    window = webview.create_window(
        title="WhatsApp Media Suite",
        url=(assets_dir / "index.html").resolve().as_uri(),
        js_api=api,
        width=560,
        height=900,
        min_size=(480, 640),
        resizable=True,
        background_color="#ece5dd",
    )

    api.set_window(window)
    webview.start(debug=False)


if __name__ == "__main__":
    main()

"""Allow running as: python -m cli.tui"""

from cli.tui.app import XnchTuiApp


def main() -> None:
    app = XnchTuiApp()
    app.run()


if __name__ == "__main__":
    main()

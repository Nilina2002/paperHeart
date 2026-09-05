"""Entry point for the local iLovePDF-style desktop app.

Run with:  python main.py
"""

from ui import App


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

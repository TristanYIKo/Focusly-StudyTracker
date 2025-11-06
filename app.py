import os, sys
from PySide6.QtWidgets import QApplication
from FrontEnd.ui_main import MainWindow

def resource_path(relative_path):
    # works in dev and in PyInstaller .exe
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

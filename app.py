import sys
from PySide6.QtWidgets import QApplication
from FrontEnd.ui_main import MainWindow

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

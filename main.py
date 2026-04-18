# -----------------------------------------------------------------------------
# QShare - A simple file sharing app for Windows 10/11
#
# by Andreas Zahnleiter <a.zahnleiter@gmx.de>
# -----------------------------------------------------------------------------
# 2026-04-04 - az - created
# 2026-04-06 - az - implemented flask and directory rendering
# 2026-04-07 - az - MainWindow with Open Directory dialog
# 2026-04-07 - az - v1.0
# 2026-07-08 - az - show QR Code in own window, not in browser
# 2026-07-08 - az - run flask process in separate thread
# 2026-07-08 - az - v1.1
# 2026-04-16 - az - User-defined login credentials; OS platform check
# 2026-04-16 - az - v1.2
# -----------------------------------------------------------------------------
import ipaddress
import sys
import socket
import threading
from enum import Enum

from PySide6.QtGui import QIcon, QPixmap, QColor
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton,
    QFileDialog, QVBoxLayout, QLabel, QCheckBox, QLineEdit, QMessageBox
)
from PySide6.QtCore import Qt

import win32security
import os
import datetime as dt
import pyqrcode
from flask import Flask, request, render_template, url_for, redirect, abort, send_file
from pathlib import Path
from werkzeug.security import safe_join
import datetime
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# -----------------------------------------------------------------------------

class LoginMethod(Enum):
    WIN_AUTH = 1
    USR_AUTH = 2

# -----------------------------------------------------------------------------

class AppGlobal:
    def __init__(self):
        # App
        self.title = "QShare App"
        self.version = "v1.2"

        # Server
        self.app = Flask(__name__)
        self.IP = ""
        self.PORT = 5100
        self.access_granted = False
        self.folder_path = ""

        # Login
        self.login_method = LoginMethod.WIN_AUTH
        self.username = ""
        self.password = ""

appGlobal = AppGlobal()

# -----------------------------------------------------------------------------

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(appGlobal.title + " " + appGlobal.version)

        app_icon = QIcon(resource_path("static\\icon-app.png"))
        self.setWindowIcon(app_icon)

        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowCloseButtonHint
        )

        # Layout
        layout = QVBoxLayout()

        # Label
        label = QLabel("QShare")

        label.setFixedSize(300, 50)
        label.setAlignment(Qt.AlignHCenter)

        # Font
        font = label.font()
        font.setBold(True)
        font.setPointSize(24)
        label.setFont(font)

        # Color
        label.setStyleSheet("color: green;")

        layout.addWidget(label)

        # Checkbox Use Windows Auth
        useWindowsAuthChk = QCheckBox("Use Windows Authentification")

        useWindowsAuthChk.setChecked(False)

        if appGlobal.login_method == LoginMethod.WIN_AUTH:
            useWindowsAuthChk.setChecked(True)

        useWindowsAuthChk.checkStateChanged.connect(self.changed_login_method)
        layout.addWidget(useWindowsAuthChk)
        self.useWindowsAuthChk = useWindowsAuthChk

        # User defined login credentials
        layout.addWidget(QLabel("Username: "))
        editUsername = QLineEdit()
        editUsername.setEnabled(not useWindowsAuthChk.isChecked())
        layout.addWidget(editUsername)
        self.editUsername = editUsername

        layout.addWidget(QLabel("Password: "))
        editPassword = QLineEdit()
        editPassword.setEchoMode(QLineEdit.EchoMode.Password)
        editPassword.setEnabled(not useWindowsAuthChk.isChecked())
        layout.addWidget(editPassword)
        self.editPassword = editPassword

        # Select folder
        button = QPushButton("Select folder...")
        button.clicked.connect(self.select_directory)
        layout.addWidget(button)

        # Start Server
        btnStartServer = QPushButton("Start server...")
        btnStartServer.clicked.connect(self.start_server)
        layout.addWidget(btnStartServer)

        # Layout
        self.setLayout(layout)

    # -----------------------------------------------------------------------------

    def select_directory(self):
        if not self.useWindowsAuthChk.isChecked():
            if len(self.editUsername.text()) == 0 or len(self.editPassword.text()) == 0:
                QMessageBox.information(None,
                                        "Warning", "Please set your login credentials first!")
                return

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select folder to share"
        )

        if directory:
            appGlobal.folder_path = directory

    # -----------------------------------------------------------------------------

    def start_server(self):
        global qr_win

        if appGlobal.folder_path:
            if appGlobal.login_method == LoginMethod.USR_AUTH:
                appGlobal.username = self.editUsername.text()
                appGlobal.password = self.editPassword.text()

            qr_win.gen_qr()
            qr_win.load_qr()
            qr_win.show()

            self.close()
        else:
            QMessageBox.information(None,
                                    "Warning", "Please select a folder!")

    # -----------------------------------------------------------------------------

    def changed_login_method(self):
        if self.useWindowsAuthChk.isChecked():
            appGlobal.login_method = LoginMethod.WIN_AUTH
        else:
            appGlobal.login_method = LoginMethod.USR_AUTH

        self.editUsername.setEnabled(appGlobal.login_method == LoginMethod.USR_AUTH)
        self.editPassword.setEnabled(appGlobal.login_method == LoginMethod.USR_AUTH)

# -----------------------------------------------------------------------------

class QRWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._server_started = False

        self.setWindowTitle("Scan QR Code")

        app_icon = QIcon(resource_path("static\\icon-app.png"))
        self.setWindowIcon(app_icon)

        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowCloseButtonHint
        )

        layout = QVBoxLayout()
        self.layout = layout

        pic = QLabel(self)
        self.pic = pic

        layout.addWidget(pic)
        self.setLayout(layout)

    # -----------------------------------------------------------------------------

    def load_qr(self):
        image_path = resource_path("static\\myqr.svg");

        pixmap = QPixmap(image_path)

        if pixmap.isNull():
            print("Error: Image not found:", image_path)

        self.pic.setPixmap(pixmap)
        self.pic.setScaledContents(True)

    # -----------------------------------------------------------------------------

    def gen_qr(self):
        fn_svg = resource_path("static\\myqr.svg")

        url = pyqrcode.create(appGlobal.IP)
        url.svg(fn_svg, scale=8)

    # -----------------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)

        if not self._server_started:
            self._server_started = True
            self.start_server()

    # -----------------------------------------------------------------------------

    def start_server(self):
        thread = threading.Thread(target=self.run_server, daemon=True)
        thread.start()

    # -----------------------------------------------------------------------------

    def run_server(self):
        appGlobal.app.run(host="0.0.0.0", port=appGlobal.PORT, use_reloader=False, debug=False)

# -----------------------------------------------------------------------------

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)

    return os.path.join(os.path.abspath("."), relative_path)

# -----------------------------------------------------------------------------

def authenticate(username, password):
    if appGlobal.login_method == LoginMethod.WIN_AUTH:
        try:
            token = win32security.LogonUser(username, ".", password,
                win32security.LOGON32_LOGON_INTERACTIVE, win32security.LOGON32_PROVIDER_DEFAULT)

            return True
        except Exception as e:
            print(f"Authentication failed: {e}")
            return False
    else:
        return (appGlobal.username == username and appGlobal.password == password)

# -----------------------------------------------------------------------------

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))

    ip = "http://" + s.getsockname()[0] + ":" + str(appGlobal.PORT)

    return ip

# -----------------------------------------------------------------------------

@appGlobal.app.route('/')
def index():
    if not appGlobal.access_granted:
        return redirect(url_for('login'))

    return redirect(url_for('access'))

# -----------------------------------------------------------------------------

@appGlobal.app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if authenticate(username, password):
            appGlobal.access_granted = True
            return redirect(url_for('access'))
        else:
            return render_template('login-failed.html.j2')

    return render_template('login.html.j2')

# -----------------------------------------------------------------------------

@appGlobal.app.route('/access')
def access():
    if not appGlobal.access_granted:
        return redirect(url_for('login'))

    return redirect(url_for('files'))

# -----------------------------------------------------------------------------

@appGlobal.app.route('/files/', defaults={'req_path': ''})
@appGlobal.app.route('/files/<path:req_path>')
def files(req_path):
    if not appGlobal.access_granted:
        return redirect(url_for('login'))

    # Join the base and the requested path
    # could have done os.path.join, but safe_join ensures that files are not fetched from parent folders of the base folder
    abs_path = safe_join(appGlobal.folder_path, req_path)

    # Return 404 if path doesn't exist
    if not os.path.exists(abs_path):
        return abort(404)

    # Check if path is a file and serve
    if os.path.isfile(abs_path):
        return send_file(abs_path)

    # Show directory contents
    def f_obj_from_scan(x):
        file_stat = x.stat()

        # return file information for rendering
        return {'name': x.name,
                'f_icon': "bi bi-folder-fill" if os.path.isdir(x.path) else get_icon_class_for_filename(x.name),
                'rel_path': os.path.relpath(x.path, appGlobal.folder_path).replace("\\", "/"),
                'm_time': get_time_stamp_string(file_stat.st_mtime),
                'size': get_readable_byte_size(file_stat.st_size)}

    file_objs = [f_obj_from_scan(x) for x in os.scandir(abs_path)]

    # get parent directory url
    parent_folder_path = os.path.relpath(
        Path(abs_path).parents[0], appGlobal.folder_path).replace("\\", "/")

    return render_template('files.html.j2', data={'files': file_objs,
                                                 'parent_folder': parent_folder_path})

# -----------------------------------------------------------------------------

def get_readable_byte_size(num, suffix='B') -> str:
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0

    return "%.1f%s%s" % (num, 'Y', suffix)

# -----------------------------------------------------------------------------

def get_time_stamp_string(t_sec: float) -> str:
    t_obj = dt.datetime.fromtimestamp(t_sec)
    t_str = dt.datetime.strftime(t_obj, '%Y-%m-%d %H:%M:%S')

    return t_str

# -----------------------------------------------------------------------------

def get_icon_class_for_filename(f_name):
    file_ext = Path(f_name).suffix
    file_ext = file_ext[1:] if file_ext.startswith(".") else file_ext

    file_types = ["aac", "ai", "bmp", "cs", "css", "csv", "doc", "docx", "exe", "gif", "heic", "html",
                  "java", "jpg", "js", "json", "jsx", "key", "m4p", "md", "mdx", "mov", "mp3",
                 "mp4", "otf", "pdf", "php", "png", "pptx", "psd", "py", "raw", "rb", "sass",
                  "scss", "sh", "sql", "svg", "tiff", "tsx", "ttf", "txt", "wav", "woff", "xlsx", "xml", "yml"]

    file_icon_class = f"bi bi-filetype-{file_ext}" if file_ext in file_types else "bi bi-file-earmark"

    return file_icon_class

# -----------------------------------------------------------------------------

if __name__ == '__main__':
    version = sys.getwindowsversion()

    if sys.platform != "win32":
        print("Your operating system is not supported! Windows only!")

    if version.major < 10:
        print("Your version of Windows is not supported! Windows 10 or later!")
        sys.exit(-1)

    # Change the directory to app path
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Finding the IP address of the PC
    appGlobal.IP = get_ip()

    # Create QT App
    qt_app = QApplication(sys.argv)

    window = MainWindow()
    window.resize(300, 100)
    window.show()

    qr_win = QRWindow()
    qr_win.resize(300, 100)

    qt_app.exec()

    # Finish!
    sys.exit(0)

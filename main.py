# -----------------------------------------------------------------------------
# QShare - A simple file sharing app
#
# by Andreas Zahnleiter <a.zahnleiter@gmx.de>
# -----------------------------------------------------------------------------
# 2026-04-04 - az - created
# 2026-04-06 - az - implemented flask and directory rendering
# -----------------------------------------------------------------------------

import sys
import socket
import webbrowser

from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton,
    QFileDialog, QVBoxLayout
)
from PySide6.QtCore import Qt

import win32security
import os
import datetime as dt
import pyqrcode
from flask import Flask, request, render_template, url_for, redirect, abort, send_file
from pathlib import Path
from werkzeug.security import safe_join

# -----------------------------------------------------------------------------

app = Flask(__name__)
PORT = 5100
access_granted = False
#folder_path = os.path.join(os.environ['USERPROFILE'])
folder_path = ""

# -----------------------------------------------------------------------------

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("QShare")

        button = QPushButton("Select folder...")
        button.clicked.connect(self.select_directory)

        layout = QVBoxLayout()
        layout.addWidget(button)
        self.setLayout(layout)

    def select_directory(self):
        global folder_path

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select folder to share"
        )

        if directory:
            folder_path = directory

        self.close()

# -----------------------------------------------------------------------------

def authenticate(username, password):
    try:
        token = win32security.LogonUser(username, ".", password,
            win32security.LOGON32_LOGON_INTERACTIVE, win32security.LOGON32_PROVIDER_DEFAULT)

        return True
    except Exception as e:
        print(f"Authentication failed: {e}")
        return False

# -----------------------------------------------------------------------------

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = "http://" + s.getsockname()[0] + ":" + str(PORT)

    return ip

# -----------------------------------------------------------------------------

def show_qr():
    fn_svg = os.path.dirname(os.path.abspath(__file__)) + '/static/myqr.svg'
    fn_qrh = os.path.dirname(os.path.abspath(__file__)) + '/templates/qr.html'

    url = pyqrcode.create(IP)
    url.svg(fn_svg, scale=8)

    webbrowser.open(fn_qrh)

# -----------------------------------------------------------------------------

@app.route('/')
def index():
    global access_granted

    if not access_granted:
        return redirect(url_for('login'))

    return redirect(url_for('access'))

# -----------------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    global access_granted

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if authenticate(username, password):
            access_granted = True
            return redirect(url_for('access'))
        else:
            return render_template('login-failed.html.j2')

    return render_template('login.html.j2')

# -----------------------------------------------------------------------------

@app.route('/access')
def access():
    global access_granted

    if not access_granted:
        return redirect(url_for('login'))

    return redirect(url_for('files'))

# -----------------------------------------------------------------------------

@app.route('/files/', defaults={'req_path': ''})
@app.route('/files/<path:req_path>')
def files(req_path):
    global access_granted

    if not access_granted:
        return redirect(url_for('login'))

    # Join the base and the requested path
    # could have done os.path.join, but safe_join ensures that files are not fetched from parent folders of the base folder
    abs_path = safe_join(folder_path, req_path)

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
                'rel_path': os.path.relpath(x.path, folder_path).replace("\\", "/"),
                'm_time': get_time_stamp_string(file_stat.st_mtime),
                'size': get_readable_byte_size(file_stat.st_size)}

    file_objs = [f_obj_from_scan(x) for x in os.scandir(abs_path)]

    # get parent directory url
    parent_folder_path = os.path.relpath(
        Path(abs_path).parents[0], folder_path).replace("\\", "/")

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
    file_types = ["aac", "ai", "bmp", "cs", "css", "csv", "doc", "docx", "exe", "gif", "heic", "html", "java", "jpg", "js", "json", "jsx", "key", "m4p", "md", "mdx", "mov", "mp3",
                 "mp4", "otf", "pdf", "php", "png", "pptx", "psd", "py", "raw", "rb", "sass", "scss", "sh", "sql", "svg", "tiff", "tsx", "ttf", "txt", "wav", "woff", "xlsx", "xml", "yml"]
    file_icon_class = f"bi bi-filetype-{file_ext}" if file_ext in file_types else "bi bi-file-earmark"

    return file_icon_class

# -----------------------------------------------------------------------------

# changing the directory to access the files desktop with the help of os module
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# finding the IP address of the PC
IP = get_ip()

if __name__ == '__main__':
    qt_app = QApplication(sys.argv)

    window = MainWindow()
    window.resize(300, 100)
    window.show()

    qt_app.exec()

    if folder_path:
        # show QR code
        show_qr()

        # run server
        app.run(host="0.0.0.0", port=PORT)

    sys.exit(0)


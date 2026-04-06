# -----------------------------------------------------------------------------
# QShare
# by Andreas Zahnleiter <a.zahnleiter@gmx.de>
# -----------------------------------------------------------------------------
# 2026-04-04 - az - created
# -----------------------------------------------------------------------------

import socket
import webbrowser
import win32security
import os
import pyqrcode
from flask import Flask, request, render_template

# -----------------------------------------------------------------------------

app = Flask(__name__)
PORT = 5100

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
    fn_svg = os.path.join(os.environ['USERPROFILE'], 'myqr.svg')
    fn_qrh = os.path.dirname(os.path.abspath(__file__)) + '/templates/qr.html'

    url = pyqrcode.create(IP + "/login")
    url.svg(fn_svg, scale=8)

    webbrowser.open(fn_qrh)

# -----------------------------------------------------------------------------

@app.route('/')
def hello_world():
    return 'Hello World'

# -----------------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if authenticate(username, password):
            return f"Hello {username}, POST request received"
        else:
            return f"Login failed"

    return render_template('login.html')

# -----------------------------------------------------------------------------

# changing the directory to access the files desktop with the help of os module
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# finding the IP address of the PC
IP = get_ip()

# show QR code
show_qr()

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=PORT)


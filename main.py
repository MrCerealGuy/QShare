import http.server
import socket
import socketserver
import webbrowser
import win32security
import pyqrcode
import os

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
    ip = "http://" + s.getsockname()[0] + ":" + str(PORT) + "/login.html"

    return ip

# -----------------------------------------------------------------------------

def show_qr():
    fn_svg = os.path.join(os.environ['USERPROFILE'], 'myqr.svg')
    fn_qrh = os.path.dirname(os.path.abspath(__file__)) + '/qr.html'

    url = pyqrcode.create(IP)
    url.svg(fn_svg, scale=8)

    webbrowser.open(fn_qrh)

# -----------------------------------------------------------------------------

def listen():
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print("serving at port", PORT)
        print("Type this in your Browser", IP)
        print("or Use the QRCode")

        httpd.serve_forever()

        #authenticate(username, password):

# -----------------------------------------------------------------------------

# assigning the appropriate port value
PORT = 8010

# changing the directory to access the files desktop with the help of os module
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# creating a http request
Handler = http.server.SimpleHTTPRequestHandler

# finding the IP address of the PC
IP = get_ip()

show_qr()

# continuous stream of data between client and server
listen()


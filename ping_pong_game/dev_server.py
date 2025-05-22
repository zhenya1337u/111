import http.server
import socketserver
import os

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        if self.path == '/':
            self.path = '/index.html'
        
        # Check if the file exists
        filepath = os.path.join(DIRECTORY, self.path.lstrip('/'))
        if not os.path.exists(filepath):
            # If index.html is requested and doesn't exist, do not error out
            if self.path == '/index.html':
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><body><h1>Hello World!</h1> <p>index.html not found, but server is running.</p></body></html>")
                return
            else:
                # For other files, if they don't exist, it's a 404
                self.send_error(404, "File not found")
                return
        
        super().do_GET()

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving at port {PORT} from directory {DIRECTORY}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        httpd.shutdown()

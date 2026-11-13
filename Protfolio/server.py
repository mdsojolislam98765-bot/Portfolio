import os
import sys
import json
import base64
import uuid
import mimetypes
import re
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse
import webbrowser

PORT = 5000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "portfolio_data.json")
IMAGES_DIR = os.path.join(BASE_DIR, "images")
VIDEOS_DIR = os.path.join(BASE_DIR, "videos")

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".mkv", ".avi", ".ogv"}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

MAX_DATA_SIZE = 50 * 1024 * 1024        # 50 MB JSON
MAX_UPLOAD_SIZE = 500 * 1024 * 1024     # 500 MB Video/Image Upload

class PortfolioServerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def send_security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Accept-Ranges", "bytes")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_security_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/admin":
            self.send_response(302)
            self.send_header("Location", "/admin.html")
            self.send_security_headers()
            self.end_headers()
            return

        if path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_security_headers()
            self.end_headers()
            self.wfile.write(json.dumps({"online": True, "port": PORT, "version": "2.0"}).encode("utf-8"))
            return

        if path == "/api/data":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_security_headers()
            self.end_headers()
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    self.wfile.write(f.read().encode("utf-8"))
            else:
                self.wfile.write(b"{}")
            return

        # Video Streaming with HTTP 206 Partial Content (Range requests)
        # This allows fast seeking, timeline scrub, and glitch-free HTML5 video playback
        clean_path = urllib.parse.unquote(path.lstrip("/"))
        file_path = os.path.join(BASE_DIR, clean_path)

        if os.path.isfile(file_path):
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext in VIDEO_EXTENSIONS:
                self.handle_video_streaming(file_path, file_ext)
                return

        super().do_GET()

    def handle_video_streaming(self, file_path, file_ext):
        try:
            file_size = os.path.getsize(file_path)
            content_type = mimetypes.guess_type(file_path)[0] or "video/mp4"
            range_header = self.headers.get("Range")

            if range_header:
                # Parse Range: bytes=start-end
                range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
                if range_match:
                    start = int(range_match.group(1))
                    end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
                    if start >= file_size:
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{file_size}")
                        self.send_security_headers()
                        self.end_headers()
                        return

                    length = end - start + 1
                    self.send_response(206)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                    self.send_header("Content-Length", str(length))
                    self.send_security_headers()
                    self.end_headers()

                    with open(file_path, "rb") as f:
                        f.seek(start)
                        bytes_to_send = length
                        chunk_size = 64 * 1024
                        while bytes_to_send > 0:
                            chunk = f.read(min(chunk_size, bytes_to_send))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            bytes_to_send -= len(chunk)
                    return

            # Normal full file response
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(file_size))
            self.send_security_headers()
            self.end_headers()

            with open(file_path, "rb") as f:
                chunk_size = 64 * 1024
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            try:
                self.send_response(500)
                self.end_headers()
            except Exception:
                pass

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/data":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > MAX_DATA_SIZE:
                self.send_response(413)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": f"Payload exceeds {MAX_DATA_SIZE // (1024*1024)}MB limit"}).encode("utf-8"))
                return

            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                if not isinstance(data, dict):
                    raise ValueError("Data must be a valid JSON object")

                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                # Auto-sync portfolio_data.js for static hosting fallback
                try:
                    js_path = os.path.join(BASE_DIR, "portfolio_data.js")
                    with open(js_path, "w", encoding="utf-8") as f_js:
                        f_js.write(f"// Auto-generated by Sojol Admin Engine\nwindow.PORTFOLIO_DATA = {json.dumps(data, indent=2, ensure_ascii=False)};\n")
                except Exception:
                    pass
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "message": "Saved securely!"}).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
            return

        if path in ("/api/upload", "/api/upload-video"):
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "Empty upload request"}).encode("utf-8"))
                return

            if content_length > MAX_UPLOAD_SIZE:
                self.send_response(413)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": f"File exceeds {MAX_UPLOAD_SIZE // (1024*1024)}MB limit"}).encode("utf-8"))
                return

            content_type = self.headers.get("Content-Type", "").lower()

            try:
                # 1. DIRECT BINARY STREAMING (application/octet-stream or video/* or image/*)
                if not content_type.startswith("application/json") and not content_type.startswith("multipart/form-data"):
                    raw_filename = self.headers.get("X-Filename", "")
                    if raw_filename:
                        raw_filename = urllib.parse.unquote(raw_filename)
                    else:
                        query_params = urllib.parse.parse_qs(parsed.query)
                        raw_filename = query_params.get("filename", ["video.mp4"])[0]

                    raw_filename = os.path.basename(raw_filename)
                    ext = ".mp4" if path == "/api/upload-video" else ".png"
                    if "." in raw_filename:
                        cand = os.path.splitext(raw_filename)[1].lower()
                        if cand in ALLOWED_EXTENSIONS:
                            ext = cand

                    is_video = ext in VIDEO_EXTENSIONS
                    target_dir = VIDEOS_DIR if is_video else IMAGES_DIR
                    os.makedirs(target_dir, exist_ok=True)

                    prefix = "video" if is_video else "upload"
                    safe_name = f"{prefix}_{uuid.uuid4().hex[:12]}{ext}"
                    target_path = os.path.join(target_dir, safe_name)

                    # Stream directly in 64KB chunks to disk - zero RAM overhead!
                    bytes_remaining = content_length
                    with open(target_path, "wb") as f:
                        while bytes_remaining > 0:
                            chunk = self.rfile.read(min(65536, bytes_remaining))
                            if not chunk:
                                break
                            f.write(chunk)
                            bytes_remaining -= len(chunk)

                    relative_url = f"videos/{safe_name}" if is_video else f"images/{safe_name}"
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_security_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True, "path": relative_url, "isVideo": is_video, "filename": raw_filename}).encode("utf-8"))
                    return

                # 2. MULTIPART / FORM-DATA UPLOAD
                if content_type.startswith("multipart/form-data"):
                    # Extract boundary
                    boundary = None
                    for part in content_type.split(";"):
                        part = part.strip()
                        if part.startswith("boundary="):
                            boundary = part[9:].strip('"').strip("'").encode("utf-8")
                            break

                    if not boundary:
                        raise ValueError("Missing multipart boundary")

                    raw_body = self.rfile.read(content_length)
                    delimiter = b"--" + boundary
                    parts = raw_body.split(delimiter)

                    file_bytes = None
                    raw_filename = "video.mp4" if path == "/api/upload-video" else "image.png"

                    for p in parts:
                        if b'filename="' in p:
                            headers_part, _, data_part = p.partition(b"\r\n\r\n")
                            # strip trailing CRLF
                            if data_part.endswith(b"\r\n"):
                                data_part = data_part[:-2]
                            file_bytes = data_part

                            # parse filename
                            fn_match = re.search(r'filename="([^"]+)"', headers_part.decode("utf-8", errors="ignore"))
                            if fn_match:
                                raw_filename = os.path.basename(fn_match.group(1))
                            break

                    if file_bytes is None:
                        raise ValueError("No file content found in multipart request")

                    ext = ".mp4" if path == "/api/upload-video" else ".png"
                    if "." in raw_filename:
                        cand = os.path.splitext(raw_filename)[1].lower()
                        if cand in ALLOWED_EXTENSIONS:
                            ext = cand

                    is_video = ext in VIDEO_EXTENSIONS
                    target_dir = VIDEOS_DIR if is_video else IMAGES_DIR
                    os.makedirs(target_dir, exist_ok=True)

                    prefix = "video" if is_video else "upload"
                    safe_name = f"{prefix}_{uuid.uuid4().hex[:12]}{ext}"
                    target_path = os.path.join(target_dir, safe_name)

                    with open(target_path, "wb") as f:
                        f.write(file_bytes)

                    relative_url = f"videos/{safe_name}" if is_video else f"images/{safe_name}"
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_security_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True, "path": relative_url, "isVideo": is_video, "filename": raw_filename}).encode("utf-8"))
                    return

                # 3. JSON BASE64 UPLOAD (Backward compatibility)
                body = self.rfile.read(content_length).decode("utf-8")
                payload = json.loads(body)
                base64_data = payload.get("video") or payload.get("image") or payload.get("file", "")
                raw_filename = os.path.basename(payload.get("filename", "file.mp4"))
                
                if "," in base64_data:
                    base64_data = base64_data.split(",")[1]
                
                file_bytes = base64.b64decode(base64_data)
                
                ext = ".mp4" if path == "/api/upload-video" else ".png"
                if "." in raw_filename:
                    candidate_ext = os.path.splitext(raw_filename)[1].lower()
                    if candidate_ext in ALLOWED_EXTENSIONS:
                        ext = candidate_ext
                
                is_video = ext in VIDEO_EXTENSIONS
                target_dir = VIDEOS_DIR if is_video else IMAGES_DIR
                os.makedirs(target_dir, exist_ok=True)
                
                prefix = "video" if is_video else "upload"
                safe_name = f"{prefix}_{uuid.uuid4().hex[:12]}{ext}"
                target_path = os.path.join(target_dir, safe_name)
                
                with open(target_path, "wb") as f:
                    f.write(file_bytes)
                
                relative_url = f"videos/{safe_name}" if is_video else f"images/{safe_name}"
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "path": relative_url, "isVideo": is_video, "filename": raw_filename}).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_security_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
            return

        super().do_POST()

def run():
    port = PORT
    server = None
    # Bind to localhost 127.0.0.1 for high security
    for p in range(PORT, PORT + 20):
        try:
            server = HTTPServer(("127.0.0.1", p), PortfolioServerHandler)
            port = p
            break
        except OSError:
            continue

    if not server:
        print("Could not bind to any port.")
        sys.exit(1)

    url = f"http://localhost:{port}"
    admin_url = f"http://localhost:{port}/admin.html"
    print("=" * 60)
    print(f"  Sojol Visuals Portfolio Server Running (SECURE)!")
    print(f"  Portfolio URL:   {url}")
    print(f"  Admin Panel URL: {admin_url}")
    print(f"  Streaming:       Enabled (HTTP 206 Partial Content)")
    print(f"  Direct Upload:   Enabled (Up to 500MB)")
    print("=" * 60)
    print("Press Ctrl+C to stop the server.")

    if len(sys.argv) > 1 and sys.argv[1] == "--open-admin":
        webbrowser.open(admin_url)
    elif len(sys.argv) > 1 and sys.argv[1] == "--open":
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.server_close()

if __name__ == "__main__":
    run()

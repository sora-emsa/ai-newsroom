import http.server
import socketserver
import json
import os
import threading
from engine import get_state, run_newsroom_cycle, start_scheduler_thread, DB_PATH
import sqlite3

PORT = 3333
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

class NewsroomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self):
        if self.path == "/api/state":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            state = get_state()
            self.wfile.write(json.dumps(state).encode("utf-8"))
        elif self.path == "/api/history":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute("SELECT id, title, category, source, url, summary_id, sent_to_telegram, created_at FROM processed_news ORDER BY created_at DESC LIMIT 30")
                rows = cur.fetchall()
                conn.close()
                items = [
                    {"id": r[0], "title": r[1], "category": r[2], "source": r[3], "url": r[4], "summary": r[5], "sent_tg": r[6], "created_at": r[7]}
                    for r in rows
                ]
                self.wfile.write(json.dumps({"history": items}).encode("utf-8"))
            except Exception as e:
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/trigger":
            # Run manual cycle in background thread
            threading.Thread(target=run_newsroom_cycle, daemon=True).start()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "triggered", "message": "Newsroom cycle started!"}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

def run_server():
    # Start the 2-hour scheduler
    print("[SERVER] Memulai background scheduler (2 jam sekali)...")
    start_scheduler_thread()

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), NewsroomHandler) as httpd:
        print(f"🚀 [PIXEL VIRTUAL OFFICE DASHBOARD] Berjalan di: http://localhost:{PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()

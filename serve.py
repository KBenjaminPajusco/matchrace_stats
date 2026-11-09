"""Serveur du site (statique) : multi-requêtes + fichiers pré-compressés (*.gz) + cache navigateur.
    python serve.py [port]   (défaut 8830)"""
import sys, os, pathlib, http.server, socketserver

ROOT = pathlib.Path(__file__).parent / "site"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8830


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)

    def send_head(self):
        path = self.translate_path(self.path)
        gz = path + ".gz"
        if os.path.isfile(path) and os.path.isfile(gz) and "gzip" in self.headers.get("Accept-Encoding", ""):
            f = open(gz, "rb")
            st = os.fstat(f.fileno())
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(st.st_size))
            self.send_header("Cache-Control", "no-cache")          # revalidé à chaque visite, servi du cache si inchangé
            self.send_header("Last-Modified", self.date_time_string(st.st_mtime))
            self.end_headers()
            return f
        return super().send_head()

    def end_headers(self):
        p = self.path.split("?")[0]
        if p.startswith(("/flags/", "/photos/", "/vendor/")):
            self.send_header("Cache-Control", "public, max-age=604800")
        super().end_headers()

    def log_message(self, *a):
        pass


class S(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    print(f"Match Race Stats : http://localhost:{PORT}")
    S(("0.0.0.0", PORT), H).serve_forever()

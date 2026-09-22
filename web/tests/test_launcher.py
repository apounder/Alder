"""Check the optional localhost launcher with stdlib only."""
import importlib.util
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("launcher", root / "portable/launch_local.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
server = launcher.ThreadingHTTPServer(("127.0.0.1", 0), launcher.Handler)
thread = Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    url = f"http://127.0.0.1:{server.server_port}"
    with urlopen(url + "/MolStudio.html") as response:
        assert response.status == 200
        assert response.headers.get_content_type() == "text/html"
        assert response.read() == launcher.APP.read_bytes()
    for path in ("/launch_local.py", "/../README.md", "/%2e%2e/README.md"):
        try:
            urlopen(url + path)
            raise AssertionError("Launcher served an unexpected file")
        except HTTPError as error:
            assert error.code == 404
    assert server.server_address[0] == "127.0.0.1"
    print("PASS localhost serves the exact portable HTML, binds loopback only, rejects other paths")
finally:
    server.shutdown()
    server.server_close()
    thread.join()

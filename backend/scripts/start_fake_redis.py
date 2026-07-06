from __future__ import annotations

import os
from contextlib import suppress

from fakeredis import TcpFakeServer


def main() -> None:
    host = os.environ.get("PLAYWRIGHT_REDIS_HOST", "127.0.0.1")
    port = int(os.environ.get("PLAYWRIGHT_REDIS_PORT", "6390"))
    server = TcpFakeServer((host, port), server_type="redis")
    try:
        server.serve_forever()
    finally:
        with suppress(Exception):
            server.shutdown()
        with suppress(Exception):
            server.server_close()


if __name__ == "__main__":
    main()

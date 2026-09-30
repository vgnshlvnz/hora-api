"""Container health check. Exit 0 if healthy, 1 otherwise.

python healthcheck.py api [port]   GET /readyz must return 200 (ephemeris + profiles load)
python healthcheck.py mcp [port]   the MCP endpoint must answer; any HTTP status counts
                                   (an unauthenticated request gets 401, which proves it is up)
"""

import sys
import urllib.error
import urllib.request

DEFAULTS = {"api": (8000, "/readyz"), "mcp": (8765, "/mcp")}


def check(kind: str, port: int | None = None, host: str = "127.0.0.1") -> bool:
    default_port, path = DEFAULTS[kind]
    url = f"http://{host}:{port or default_port}{path}"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return kind == "mcp" or response.status == 200
    except urllib.error.HTTPError:
        return kind == "mcp"  # for the API any error status (503 not ready) is unhealthy
    except (urllib.error.URLError, OSError):
        return False


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in DEFAULTS:
        print(__doc__, file=sys.stderr)
        return 2
    port = int(argv[1]) if len(argv) > 1 else None
    return 0 if check(argv[0], port) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

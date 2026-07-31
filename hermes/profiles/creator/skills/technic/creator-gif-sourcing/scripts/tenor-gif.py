#!/usr/bin/env python3
"""Search Tenor and download a selected result without exposing the API key."""

import argparse
from contextlib import contextmanager
import ipaddress
import json
import os
import signal
import socket
import sys
import tempfile
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


API_URL = "https://tenor.googleapis.com/v2/search"
USER_AGENT = "creator-gif-sourcing/1.0"
FORMATS = ("gif", "tinygif", "mp4", "tinymp4", "webm", "nanogif")
API_HOSTS = ("tenor.googleapis.com",)
MEDIA_HOSTS = ("media.tenor.com",)
ITEM_HOSTS = ("tenor.com",)
MAX_SEARCH_BYTES = 5 * 1024 * 1024
MAX_RESULTS_BYTES = 5 * 1024 * 1024
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
MAX_NETWORK_SECONDS = 60
CONTENT_TYPES = {
    "gif": "image/gif",
    "tinygif": "image/gif",
    "nanogif": "image/gif",
    "mp4": "video/mp4",
    "tinymp4": "video/mp4",
    "webm": "video/webm",
}
DOWNLOAD_CHUNK_BYTES = 1024 * 1024


class RejectRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


OPENER = build_opener(RejectRedirectHandler())


class NetworkTimeoutError(TimeoutError):
    pass


def raise_network_timeout(signum: int, frame: object) -> None:
    raise NetworkTimeoutError


@contextmanager
def network_timeout(seconds: float):
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_remaining, previous_interval = signal.getitimer(signal.ITIMER_REAL)
    started = time.monotonic()
    timer_seconds = seconds
    if previous_remaining > 0:
        timer_seconds = min(timer_seconds, previous_remaining)

    signal.signal(signal.SIGALRM, raise_network_timeout)
    try:
        signal.setitimer(signal.ITIMER_REAL, timer_seconds)
    except BaseException:
        signal.signal(signal.SIGALRM, previous_handler)
        raise

    try:
        yield
    finally:
        elapsed = time.monotonic() - started
        remaining = previous_remaining - elapsed
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if remaining > 0:
            signal.setitimer(signal.ITIMER_REAL, remaining, previous_interval)
        elif previous_interval > 0:
            signal.setitimer(
                signal.ITIMER_REAL, previous_interval, previous_interval
            )


def scrub(value: object, secret: str) -> object:
    """Remove a secret from selected JSON values and display text."""
    if isinstance(value, str):
        return value.replace(secret, "[REDACTED]") if secret else value
    if isinstance(value, list):
        return [scrub(item, secret) for item in value]
    if isinstance(value, dict):
        return {key: scrub(item, secret) for key, item in value.items()}
    return value


def is_allowed_url(value: object, allowed_hosts: tuple[str, ...]) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme.lower() != "https"
        or not parsed.netloc
        or hostname not in allowed_hosts
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        return False
    try:
        addresses = socket.getaddrinfo(hostname, port or 443, type=socket.SOCK_STREAM)
    except NetworkTimeoutError:
        raise
    except (OSError, ValueError):
        return False
    if not addresses:
        return False
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address[4][0])
        except (IndexError, ValueError):
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
            or not ip.is_global
        ):
            return False
    return True


def report_network_error(error: Exception) -> None:
    if isinstance(error, HTTPError):
        print("HTTP request failed.", file=sys.stderr)
    else:
        print("Network request failed.", file=sys.stderr)


def response_content_length(response: object, limit: int) -> int | None:
    headers = getattr(response, "headers", None)
    value = headers.get("Content-Length") if headers is not None else None
    if value is None:
        return None
    try:
        length = int(value)
    except (TypeError, ValueError):
        raise ValueError("invalid content length")
    if length < 0 or length > limit:
        raise ValueError("response too large")
    return length


def read_bounded(response: object, limit: int) -> bytes:
    response_content_length(response, limit)
    data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("response too large")
    return data


def output_parent(path: str) -> str | None:
    parent = os.path.dirname(os.path.abspath(path))
    return parent if os.path.isdir(parent) else None


def write_json(path: str, payload: dict[str, object]) -> bool:
    parent = output_parent(path)
    if parent is None:
        print("Output parent directory does not exist.", file=sys.stderr)
        return False

    temporary_path = None
    try:
        descriptor, temporary_path = tempfile.mkstemp(
            dir=parent, prefix=".tenor-results-", suffix=".tmp"
        )
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
        return True
    except (OSError, TypeError, ValueError):
        print("Could not write output JSON.", file=sys.stderr)
        return False
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass


def media_entry(
    value: object, format_name: str, secret: str
) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    url = value.get("url")
    if not is_allowed_url(url, MEDIA_HOSTS) or (secret and secret in url):
        return None
    return scrub(
        {
            "url": url,
            "format": format_name,
            "dims": value.get("dims"),
            "duration": value.get("duration"),
            "size": value.get("size"),
        },
        secret,
    )


def sanitized_results(data: object, requested_format: str, secret: str) -> list[dict[str, object]] | None:
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        return None

    clean_results = []
    for result_index, item in enumerate(data["results"]):
        if not isinstance(item, dict):
            continue
        media_formats = item.get("media_formats")
        if not isinstance(media_formats, dict):
            continue
        media = media_entry(media_formats.get(requested_format), requested_format, secret)
        if media is None:
            continue

        item_url = item.get("itemurl", item.get("item_url"))
        if not is_allowed_url(item_url, ITEM_HOSTS) or (secret and secret in item_url):
            continue

        clean_item = {
            "index": len(clean_results),
            "rank": result_index,
            "id": item.get("id") if isinstance(item.get("id"), str) else "",
            "title": item.get("title") if isinstance(item.get("title"), str) else "",
            "content_description": (
                item.get("content_description")
                if isinstance(item.get("content_description"), str)
                else ""
            ),
            "item_url": item_url,
            "created": item.get("created"),
            "media": media,
        }

        if "tags" in item and isinstance(item["tags"], list):
            clean_item["tags"] = item["tags"]

        preview = media_entry(media_formats.get("tinygif"), "tinygif", secret)
        if preview is not None:
            clean_item["preview"] = preview
        clean_results.append(scrub(clean_item, secret))

    return clean_results


def search(args: argparse.Namespace) -> int:
    try:
        api_key = os.environ["TENOR_API_KEY"]
    except KeyError:
        print("TENOR_API_KEY is missing or empty.", file=sys.stderr)
        return 2
    if not api_key:
        print("TENOR_API_KEY is missing or empty.", file=sys.stderr)
        return 2

    media_filter = args.format
    if args.format != "tinygif":
        media_filter = f"{args.format},tinygif"
    parameters = {
        "key": api_key,
        "q": args.query,
        "limit": args.limit,
        "locale": args.locale,
        "contentfilter": args.content_filter,
        "media_filter": media_filter,
    }
    request_url = f"{API_URL}?{urlencode(parameters)}"

    try:
        with network_timeout(MAX_NETWORK_SECONDS):
            if not is_allowed_url(request_url, API_HOSTS):
                print("Tenor API URL validation failed.", file=sys.stderr)
                return 1
            request = Request(
                request_url, headers={"User-Agent": USER_AGENT}, method="GET"
            )
            with OPENER.open(request, timeout=20) as response:
                response_data = json.loads(read_bounded(response, MAX_SEARCH_BYTES))
            results = sanitized_results(response_data, args.format, api_key)
    except NetworkTimeoutError:
        print("Network request timed out.", file=sys.stderr)
        return 1
    except (HTTPError, URLError) as error:
        report_network_error(error)
        return 1
    except (OSError, ValueError, json.JSONDecodeError):
        print("Could not read the Tenor response.", file=sys.stderr)
        return 1

    if results is None:
        print("Tenor returned an invalid response.", file=sys.stderr)
        return 1

    payload = {
        "query": scrub(args.query, api_key),
        "locale": scrub(args.locale, api_key),
        "content_filter": scrub(args.content_filter, api_key),
        "requested_format": scrub(args.format, api_key),
        "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "results": results,
    }
    if not write_json(args.output, payload):
        return 2
    print(f"{len(results)} result(s) saved.", file=sys.stderr)
    return 0


def download(args: argparse.Namespace) -> int:
    try:
        with open(args.results, "rb") as handle:
            results_data = handle.read(MAX_RESULTS_BYTES + 1)
        if len(results_data) > MAX_RESULTS_BYTES:
            raise ValueError("results too large")
        payload = json.loads(results_data)
    except (OSError, ValueError, json.JSONDecodeError):
        print("Could not read results JSON.", file=sys.stderr)
        return 1

    result_items = payload.get("results") if isinstance(payload, dict) else None
    selected = None
    if isinstance(result_items, list):
        for item in result_items:
            if isinstance(item, dict) and type(item.get("index")) is int:
                if item["index"] == args.index:
                    selected = item
                    break
    requested_format = payload.get("requested_format") if isinstance(payload, dict) else None
    if not isinstance(requested_format, str) or requested_format not in FORMATS:
        print("Results JSON has an invalid requested format.", file=sys.stderr)
        return 2
    media = selected.get("media") if isinstance(selected, dict) else None
    if (
        not isinstance(media, dict)
        or media.get("format") != requested_format
    ):
        print("Selected result has an invalid media format.", file=sys.stderr)
        return 2
    url = media.get("url") if isinstance(media, dict) else None

    parent = output_parent(args.output)
    if parent is None:
        print("Output parent directory does not exist.", file=sys.stderr)
        return 2

    temporary_path = None
    byte_count = 0
    prefix = bytearray()
    try:
        with network_timeout(MAX_NETWORK_SECONDS):
            if not is_allowed_url(url, MEDIA_HOSTS):
                print("Selected result has an invalid media URL.", file=sys.stderr)
                return 2
            metadata_size = media.get("size")
            has_metadata_size = type(metadata_size) is int and metadata_size > 0
            if has_metadata_size and metadata_size > MAX_DOWNLOAD_BYTES:
                print("Selected media is too large.", file=sys.stderr)
                return 2

            request = Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
            with OPENER.open(request, timeout=20) as response:
                response_content_length(response, MAX_DOWNLOAD_BYTES)
                content_type = response.headers.get("Content-Type")
                if not isinstance(content_type, str):
                    raise ValueError("missing content type")
                content_type = content_type.split(";", 1)[0].strip().lower()
                if content_type != CONTENT_TYPES[requested_format]:
                    raise ValueError("unexpected content type")
                descriptor, temporary_path = tempfile.mkstemp(
                    dir=parent, prefix=".tenor-download-", suffix=".tmp"
                )
                with os.fdopen(descriptor, "wb") as handle:
                    while True:
                        chunk = response.read(
                            min(DOWNLOAD_CHUNK_BYTES, MAX_DOWNLOAD_BYTES - byte_count + 1)
                        )
                        if not chunk:
                            break
                        if byte_count + len(chunk) > MAX_DOWNLOAD_BYTES:
                            raise ValueError("download too large")
                        if len(prefix) < 16:
                            prefix.extend(chunk[: 16 - len(prefix)])
                        handle.write(chunk)
                        byte_count += len(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
            if byte_count == 0:
                print("Downloaded file is empty.", file=sys.stderr)
                return 1
            if requested_format in ("gif", "tinygif", "nanogif"):
                valid_magic = bytes(prefix).startswith((b"GIF87a", b"GIF89a"))
            elif requested_format in ("mp4", "tinymp4"):
                valid_magic = len(prefix) >= 8 and bytes(prefix)[4:8] == b"ftyp"
            else:
                valid_magic = bytes(prefix).startswith(b"\x1a\x45\xdf\xa3")
            if not valid_magic:
                print("Downloaded media has invalid content.", file=sys.stderr)
                return 1
            if has_metadata_size and byte_count != metadata_size:
                print("Downloaded media size does not match metadata.", file=sys.stderr)
                return 1
            os.replace(temporary_path, args.output)
            temporary_path = None
    except NetworkTimeoutError:
        print("Network request timed out.", file=sys.stderr)
        return 1
    except (HTTPError, URLError) as error:
        report_network_error(error)
        return 1
    except (OSError, ValueError, TimeoutError):
        print("Could not download or save the selected GIF.", file=sys.stderr)
        return 1
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass

    print(f"{args.output} {byte_count}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search and download Tenor media safely.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="search Tenor")
    search_parser.add_argument("--query", required=True)
    search_parser.add_argument("--output", required=True)
    search_parser.add_argument("--limit", type=int, choices=range(3, 11), default=5)
    search_parser.add_argument("--locale", default="en_US")
    search_parser.add_argument(
        "--content-filter", choices=("off", "low", "medium", "high"), default="high"
    )
    search_parser.add_argument("--format", choices=FORMATS, default="gif")
    search_parser.set_defaults(handler=search)

    download_parser = subparsers.add_parser("download", help="download a selected result")
    download_parser.add_argument("--results", required=True)
    download_parser.add_argument("--index", required=True, type=int)
    download_parser.add_argument("--output", required=True)
    download_parser.set_defaults(handler=download)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())

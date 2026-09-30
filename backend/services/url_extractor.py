import ipaddress
import json
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import requests


MAX_PAGE_BYTES = 2_500_000
MAX_REDIRECTS = 3


class JobPageParser(HTMLParser):
    SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "header"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.visible = []
        self.title_parts = []
        self.meta = {}
        self.json_ld = []
        self.skip_depth = 0
        self.in_title = False
        self.in_json_ld = False
        self.json_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = (attrs.get("property") or attrs.get("name") or "").lower()
            if key and attrs.get("content"):
                self.meta[key] = attrs["content"]
        if tag == "title":
            self.in_title = True
        if tag == "script":
            self.in_json_ld = "ld+json" in attrs.get("type", "").lower()
            self.json_text = []
        if self.in_json_ld:
            return
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "script" and self.in_json_ld:
            try:
                self.json_ld.append(json.loads("".join(self.json_text)))
            except (ValueError, TypeError):
                pass
            self.in_json_ld = False
            self.json_text = []
        if tag in self.SKIP_TAGS and not self.in_json_ld:
            self.skip_depth = max(0, self.skip_depth - 1)

    def handle_data(self, data):
        if self.in_json_ld:
            self.json_text.append(data)
        elif self.in_title:
            self.title_parts.append(data)
        elif not self.skip_depth:
            text = " ".join(data.split())
            if text:
                self.visible.append(text)


def _job_posting(items):
    if isinstance(items, list):
        for item in items:
            found = _job_posting(item)
            if found:
                return found
        return None
    if not isinstance(items, dict):
        return None
    kind = items.get("@type", "")
    if kind == "JobPosting" or isinstance(kind, list) and "JobPosting" in kind:
        return items
    graph = items.get("@graph")
    return _job_posting(graph) if graph else None


def _plain_text(value):
    if not value:
        return ""
    parser = JobPageParser()
    try:
        parser.feed(str(value))
        return " ".join(parser.visible).strip()
    except (ValueError, TypeError):
        return " ".join(str(value).split())


def _validate_public_https_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("Enter a valid public HTTPS job-post URL.")
    try:
        parts = urlsplit(value.strip())
        host = (parts.hostname or "").rstrip(".").encode("idna").decode("ascii").lower()
        port = parts.port
    except (ValueError, UnicodeError):
        raise ValueError("Enter a valid public HTTPS job-post URL.") from None
    if parts.scheme.lower() != "https" or not host or parts.username or parts.password or port not in (None, 443):
        raise ValueError("Only public HTTPS job-post links on the standard secure port are supported.")
    try:
        addresses = {item[4][0].split("%", 1)[0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise ValueError("That link does not resolve to a public internet host.")
    except (socket.gaierror, OSError):
        raise ValueError("The job-post URL host could not be reached.") from None
    return parts.geturl()


def _fetch_html(url):
    current = url
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ClearhireJobPostChecker/1.0)", "Accept": "text/html,application/xhtml+xml"}
    for _ in range(MAX_REDIRECTS + 1):
        current = _validate_public_https_url(current)
        try:
            response = requests.get(current, headers=headers, timeout=(5, 12), stream=True, allow_redirects=False)
        except requests.RequestException:
            raise ValueError("Could not load that job-post page. It may block automated requests or require sign-in.") from None
        if response.is_redirect or response.is_permanent_redirect:
            destination = response.headers.get("Location")
            response.close()
            if not destination:
                raise ValueError("The job-post link returned an invalid redirect.")
            current = urljoin(current, destination)
            continue
        if response.status_code < 200 or response.status_code >= 300:
            response.close()
            raise ValueError(f"The job-post page returned HTTP {response.status_code}.")
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            response.close()
            raise ValueError("That URL did not return an HTML job-post page.")
        pieces, size = [], 0
        try:
            for piece in response.iter_content(65536):
                size += len(piece)
                if size > MAX_PAGE_BYTES:
                    raise ValueError("The linked page is too large to analyze (2.5 MB maximum).")
                pieces.append(piece)
        finally:
            response.close()
        return current, b"".join(pieces).decode(response.encoding or "utf-8", errors="replace")
    raise ValueError("That job-post URL redirected too many times.")


def extract_job_post(url):
    final_url, html = _fetch_html(url)
    parser = JobPageParser()
    parser.feed(html)
    structured = next((job for job in (_job_posting(node) for node in parser.json_ld) if job), {})
    title = str(structured.get("title") or "" ).strip() or " ".join(" ".join(parser.title_parts).split()) or parser.meta.get("og:title", "")
    description = _plain_text(structured.get("description"))
    if len(description) < 40:
        description = parser.meta.get("og:description") or parser.meta.get("description") or " ".join(parser.visible)
        description = _plain_text(description)
    if not title and not description:
        raise ValueError("No readable job details were found on that page. Try a public listing URL or paste the post text.")
    if len(description) < 40:
        raise ValueError("The page loaded, but it did not expose enough job-post text. Paste the description or try another public listing page.")
    company = structured.get("hiringOrganization", {})
    if isinstance(company, dict):
        company = company.get("name", "")
    location = structured.get("jobLocation", {})
    if isinstance(location, list):
        location = location[0] if location else {}
    address = location.get("address", {}) if isinstance(location, dict) else {}
    if isinstance(address, dict):
        location = ", ".join(str(address.get(key, "")).strip() for key in ("addressLocality", "addressRegion", "addressCountry") if address.get(key))
    else:
        location = ""
    return {"title": title[:300], "company_name": str(company or "")[:300], "location": str(location or "")[:300], "description": description[:30000], "source_url": final_url}

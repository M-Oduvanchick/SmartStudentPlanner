from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlparse

import httpx

from app.core.config import settings
from app.integrations.pnrpu.errors import InvalidScheduleFileError, ScheduleSourceError
from app.integrations.pnrpu.models import ScheduleDocument

_USER_AGENT = "SmartStudentPlanner/0.1 (+https://github.com/M-Oduvanchick/SmartStudentPlanner)"


class _SpreadsheetLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attributes = dict(attrs)
        href = attributes.get("href")
        if href is not None:
            self._href = href
            self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._href is None:
            return
        self.links.append((self._href, " ".join("".join(self._text_parts).split())))
        self._href = None
        self._text_parts = []


class PnrpuScheduleClient:
    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        *,
        base_url: str = settings.pnrpu_base_url,
        schedule_path: str = settings.pnrpu_schedule_path,
        timeout_seconds: float = settings.pnrpu_request_timeout_seconds,
        max_file_size_bytes: int = settings.pnrpu_max_schedule_file_size_bytes,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.schedule_url = urljoin(self.base_url, schedule_path)
        self.timeout_seconds = timeout_seconds
        self.max_file_size_bytes = max_file_size_bytes
        self._http_client = http_client or httpx.AsyncClient()
        self._owns_http_client = http_client is None

    async def __aenter__(self) -> "PnrpuScheduleClient":
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: object | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self._http_client.aclose()

    async def search_documents(self, group_name: str) -> list[ScheduleDocument]:
        query = " ".join(group_name.split())
        if not query:
            raise ValueError("Group name cannot be empty")
        if len(query) > 100:
            raise ValueError("Group name is too long")

        try:
            response = await self._http_client.get(
                self.schedule_url,
                params={"search": query},
                headers={"User-Agent": _USER_AGENT},
                follow_redirects=True,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise ScheduleSourceError("Failed to search the PNRPU schedule source") from error

        parser = _SpreadsheetLinkParser()
        parser.feed(response.text)

        documents: list[ScheduleDocument] = []
        seen_urls: set[str] = set()
        for href, title in parser.links:
            url = str(httpx.URL(urljoin(str(response.url), href)))
            if not self._is_allowed_spreadsheet_url(url) or url in seen_urls:
                continue
            seen_urls.add(url)
            documents.append(
                ScheduleDocument(
                    title=title or self._filename_from_url(url),
                    url=url,
                )
            )
        return documents

    async def download_document(self, document: ScheduleDocument) -> bytes:
        if not self._is_allowed_spreadsheet_url(document.url):
            raise InvalidScheduleFileError("Schedule document URL is not allowed")

        content = bytearray()
        try:
            async with self._http_client.stream(
                "GET",
                document.url,
                headers={"User-Agent": _USER_AGENT},
                follow_redirects=True,
                timeout=self.timeout_seconds,
            ) as response:
                response.raise_for_status()
                if not self._has_same_origin(str(response.url)):
                    raise InvalidScheduleFileError("Schedule download redirected to another host")

                content_length = response.headers.get("Content-Length")
                if content_length is not None:
                    try:
                        if int(content_length) > self.max_file_size_bytes:
                            raise InvalidScheduleFileError("Schedule file is too large")
                    except ValueError:
                        pass

                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > self.max_file_size_bytes:
                        raise InvalidScheduleFileError("Schedule file is too large")
        except InvalidScheduleFileError:
            raise
        except httpx.HTTPError as error:
            raise ScheduleSourceError("Failed to download the PNRPU schedule file") from error

        if not content.startswith(b"PK\x03\x04"):
            raise InvalidScheduleFileError("Downloaded document is not an XLSX file")
        return bytes(content)

    def _is_allowed_spreadsheet_url(self, url: str) -> bool:
        parsed = urlparse(url)
        return self._has_same_origin(url) and unquote(parsed.path).lower().endswith(".xlsx")

    def _has_same_origin(self, url: str) -> bool:
        return self._origin(url) == self._origin(self.base_url)

    @staticmethod
    def _origin(url: str) -> tuple[str, str | None, int | None]:
        parsed = urlparse(url)
        port = parsed.port
        if port is None:
            port = 443 if parsed.scheme == "https" else 80 if parsed.scheme == "http" else None
        return parsed.scheme.lower(), parsed.hostname, port

    @staticmethod
    def _filename_from_url(url: str) -> str:
        return unquote(urlparse(url).path).rsplit("/", maxsplit=1)[-1]

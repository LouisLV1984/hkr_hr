import re
from datetime import date
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SOURCE_URL_TEMPLATE = (
    "https://www.labour.gov.hk/tc/news/latest_holidays{year}.htm"
)
PUBLIC_SOURCE_URL_TEMPLATE = (
    "https://www.gov.hk/tc/about/abouthk/holiday/{year}.htm"
)


class HolidayImportError(ValueError):
    pass


class _HolidayTableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self._cell is not None:
            value = " ".join("".join(self._cell).split())
            self._row.append(value)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


def parse_hong_kong_statutory_holidays(
    html,
    year,
):
    parser = _HolidayTableParser()
    parser.feed(html)
    expected_match = re.search(rf"{year}年的(\d+)天法定假日", html)
    expected_count = int(expected_match.group(1)) if expected_match else None
    holidays = []

    for row in parser.rows:
        if len(row) < 3 or not re.fullmatch(r"\d+\.", row[0]):
            continue
        name = row[1].strip()
        date_matches = re.findall(r"(\d{1,2})月(\d{1,2})日", row[2])
        if not name or not date_matches:
            continue
        if len(date_matches) > 1:
            # HKR's company rule fixes the statutory-holiday choice at
            # Christmas Day. HR therefore never needs to make this annual
            # legal choice during calendar maintenance.
            index = 1
            if index >= len(date_matches):
                raise HolidayImportError("勞工處法定假日清單的可選日期格式無法識別。")
            month, day = date_matches[index]
            name = "聖誕節"
        else:
            month, day = date_matches[0]
        try:
            holiday_date = date(year, int(month), int(day))
        except ValueError as exc:
            raise HolidayImportError("勞工處法定假日清單包含無效日期。") from exc
        holidays.append((holiday_date, name))

    if not holidays:
        raise HolidayImportError("未能從勞工處頁面讀取法定假日，未有改動工作日曆。")
    if expected_count is not None and len(holidays) != expected_count:
        raise HolidayImportError(
            f"勞工處頁面列明 {expected_count} 天，但系統只讀取到 {len(holidays)} 天；"
            "為免錯誤出糧，未有匯入。"
        )
    if len({item[0] for item in holidays}) != len(holidays):
        raise HolidayImportError("勞工處法定假日清單包含重複日期，未有匯入。")
    return holidays


def fetch_hong_kong_statutory_holidays(
    year,
    timeout=15,
):
    if year < 2020 or year > 2100:
        raise HolidayImportError("法定假日年份必須介乎 2020 至 2100。")
    source_url = SOURCE_URL_TEMPLATE.format(year=year)
    request = Request(
        source_url,
        headers={"User-Agent": "HKR-HR-Work-Calendar/1.0"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            html = response.read().decode(charset)
    except (HTTPError, URLError, TimeoutError, UnicodeError) as exc:
        raise HolidayImportError(
            f"暫時無法讀取勞工處 {year} 年法定假日清單，請稍後再試。"
        ) from exc
    return parse_hong_kong_statutory_holidays(
        html,
        year,
    )


def parse_hong_kong_public_holidays(html, year):
    """Read dated general holidays; recurring Sundays remain schedule logic."""
    parser = _HolidayTableParser()
    parser.feed(html)
    holidays = []
    for row in parser.rows:
        if len(row) < 2:
            continue
        name = row[0].strip()
        match = re.fullmatch(r"(\d{1,2})月(\d{1,2})日", row[1].strip())
        if not name or not match:
            continue
        try:
            holiday_date = date(year, int(match.group(1)), int(match.group(2)))
        except ValueError as exc:
            raise HolidayImportError("政府公眾假期清單包含無效日期。") from exc
        holidays.append((holiday_date, name))

    if not holidays:
        raise HolidayImportError("未能從政府頁面讀取公眾假期，未有改動工作日曆。")
    if len({item[0] for item in holidays}) != len(holidays):
        raise HolidayImportError("政府公眾假期清單包含重複日期，未有匯入。")
    # The gazetted annual list currently contains 17 dated general holidays;
    # a lower bound catches layout changes without hard-coding future totals.
    if len(holidays) < 17:
        raise HolidayImportError(
            f"政府頁面只讀取到 {len(holidays)} 個公眾假期日期；"
            "為免錯誤出糧，未有匯入。"
        )
    return holidays


def fetch_hong_kong_public_holidays(year, timeout=15):
    if year < 2020 or year > 2100:
        raise HolidayImportError("公眾假期年份必須介乎 2020 至 2100。")
    source_url = PUBLIC_SOURCE_URL_TEMPLATE.format(year=year)
    request = Request(
        source_url,
        headers={"User-Agent": "HKR-HR-Work-Calendar/1.0"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            html = response.read().decode(charset)
    except (HTTPError, URLError, TimeoutError, UnicodeError) as exc:
        raise HolidayImportError(
            f"暫時無法讀取政府 {year} 年公眾假期清單，請稍後再試。"
        ) from exc
    return parse_hong_kong_public_holidays(html, year)

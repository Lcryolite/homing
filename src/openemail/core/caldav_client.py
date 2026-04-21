from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from xml.etree import ElementTree as ET

from openemail.models.account import Account
from openemail.models.calendar_event import CalendarEvent

logger = logging.getLogger(__name__)

CALDAV_NS = {
    "d": "DAV:",
    "c": "urn:ietf:params:xml:ns:caldav",
    "cs": "http://calendarserver.org/ns/",
}


class CalDAVClient:
    """CalDAV 客户端，支持日历列表拉取、VEVENT/VTODO 读写、最近变更同步"""

    def __init__(self, account: Account) -> None:
        self._account = account
        self._session = None

    async def connect(self) -> bool:
        try:
            import httpx

            auth = None
            headers = {}
            if self._account.auth_type == "oauth2" and self._account.oauth_token:
                headers["Authorization"] = f"Bearer {self._account.oauth_token}"
            else:
                auth = (self._account.email, self._account.password)

            base_url = getattr(self._account, "caldav_url", "")
            if not base_url:
                base_url = (
                    f"https://{self._account.imap_host.replace('imap', 'caldav', 1)}/"
                )

            self._session = httpx.AsyncClient(
                base_url=base_url,
                auth=auth,
                headers=headers,
                timeout=30.0,
            )
            return True
        except Exception as e:
            logger.error("CalDAV connect failed: %s", e)
            return False

    async def disconnect(self) -> None:
        if self._session:
            await self._session.aclose()
            self._session = None

    async def discover_calendars(self) -> list[dict]:
        """发现可用日历列表 (RFC 4791)"""
        if not self._session:
            return []

        try:
            propfind_body = """<?xml version="1.0" encoding="utf-8"?>
<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:prop>
    <d:displayname/>
    <d:resourcetype/>
    <c:supported-calendar-component-set/>
    <d:sync-token/>
  </d:prop>
</d:propfind>"""

            resp = await self._session.request(
                "PROPFIND",
                "/",
                content=propfind_body,
                headers={
                    "Depth": "1",
                    "Content-Type": "application/xml; charset=utf-8",
                },
            )

            if resp.status_code not in (207, 200):
                logger.warning("CalDAV PROPFIND returned %d", resp.status_code)
                return []

            return self._parse_calendar_multi_status(resp.text)
        except Exception as e:
            logger.error("CalDAV discover calendars failed: %s", e)
            return []

    async def get_events(
        self, calendar_url: str, start: Optional[str] = None, end: Optional[str] = None
    ) -> list[CalendarEvent]:
        """拉取日历事件 (VEVENT)"""
        if not self._session:
            return []

        try:
            time_range = ""
            if start and end:
                time_range = f'<c:time-range start="{start}" end="{end}"/>'

            report_body = f"""<?xml version="1.0" encoding="utf-8"?>
<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:prop>
    <d:getetag/>
    <c:calendar-data/>
  </d:prop>
  <c:filter>
    <c:comp-filter name="VCALENDAR">
      <c:comp-filter name="VEVENT">
        {time_range}
      </c:comp-filter>
    </c:comp-filter>
  </c:filter>
</c:calendar-query>"""

            resp = await self._session.request(
                "REPORT",
                calendar_url,
                content=report_body,
                headers={
                    "Depth": "1",
                    "Content-Type": "application/xml; charset=utf-8",
                },
            )

            if resp.status_code not in (207, 200):
                return []

            return self._parse_events_response(resp.text)
        except Exception as e:
            logger.error("CalDAV get events failed: %s", e)
            return []

    async def create_event(
        self, calendar_url: str, event: CalendarEvent
    ) -> Optional[str]:
        """创建日历事件 (PUT)"""
        if not self._session:
            return None

        try:
            ical_data = self._event_to_ical(event)
            uid = f"openemail-{event.id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            event_url = f"{calendar_url.rstrip('/')}/{uid}.ics"

            resp = await self._session.put(
                event_url,
                content=ical_data,
                headers={"Content-Type": "text/calendar; charset=utf-8"},
            )

            if resp.status_code in (201, 204):
                return event_url
            return None
        except Exception as e:
            logger.error("CalDAV create event failed: %s", e)
            return None

    async def delete_event(self, event_url: str) -> bool:
        """删除日历事件 (DELETE)"""
        if not self._session:
            return False

        try:
            resp = await self._session.delete(event_url)
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.error("CalDAV delete event failed: %s", e)
            return False

    async def sync_changes(
        self, calendar_url: str, sync_token: str = ""
    ) -> tuple[list[dict], str]:
        """
        增量同步 (RFC 6578 WebDAV Sync).

        Returns:
            (changed_items, new_sync_token)
        """
        if not self._session:
            return [], sync_token

        try:
            sync_body = f"""<?xml version="1.0" encoding="utf-8"?>
<d:sync-collection xmlns:d="DAV:">
  <d:sync-token>{sync_token}</d:sync-token>
  <d:prop>
    <d:getetag/>
    <d:getcontenttype/>
  </d:prop>
</d:sync-collection>"""

            resp = await self._session.request(
                "REPORT",
                calendar_url,
                content=sync_body,
                headers={"Content-Type": "application/xml; charset=utf-8"},
            )

            if resp.status_code == 207:
                changes, new_token = self._parse_sync_response(resp.text)
                return changes, new_token

            return [], sync_token
        except Exception as e:
            logger.error("CalDAV sync changes failed: %s", e)
            return [], sync_token

    def _parse_calendar_multi_status(self, xml_text: str) -> list[dict]:
        calendars = []
        try:
            root = ET.fromstring(xml_text)
            for response in root.findall(".//d:response", CALDAV_NS):
                href = response.find("d:href", CALDAV_NS)
                propstat = response.find(".//d:propstat/d:prop", CALDAV_NS)
                if href is None or propstat is None:
                    continue

                resourcetype = propstat.find("d:resourcetype", CALDAV_NS)
                if resourcetype is None:
                    continue

                is_calendar = resourcetype.find("c:calendar", CALDAV_NS) is not None
                if not is_calendar:
                    continue

                displayname = propstat.find("d:displayname", CALDAV_NS)
                name = (
                    displayname.text
                    if displayname is not None and displayname.text
                    else ""
                )

                sync_token_el = propstat.find("d:sync-token", CALDAV_NS)
                sync_token = sync_token_el.text if sync_token_el is not None else ""

                calendars.append(
                    {
                        "url": href.text,
                        "name": name,
                        "sync_token": sync_token,
                    }
                )
        except ET.ParseError:
            logger.warning("Failed to parse CalDAV multistatus XML")
        return calendars

    def _parse_events_response(self, xml_text: str) -> list[CalendarEvent]:
        events = []
        try:
            root = ET.fromstring(xml_text)
            for response in root.findall(".//d:response", CALDAV_NS):
                href_el = response.find("d:href", CALDAV_NS)
                caldata = response.find(".//c:calendar-data", CALDAV_NS)
                etag_el = response.find(".//d:getetag", CALDAV_NS)

                if caldata is None or caldata.text is None:
                    continue

                event = self._parse_ical_to_event(caldata.text)
                if event:
                    if href_el is not None:
                        event.sync_url = href_el.text
                    if etag_el is not None:
                        event.sync_etag = etag_el.text or ""
                    events.append(event)
        except ET.ParseError:
            logger.warning("Failed to parse CalDAV events XML")
        return events

    def _parse_ical_to_event(self, ical_text: str) -> Optional[CalendarEvent]:
        try:
            event = CalendarEvent()
            in_vevent = False
            for line in ical_text.replace("\r\n", "\n").split("\n"):
                line = line.strip()
                if line == "BEGIN:VEVENT":
                    in_vevent = True
                    continue
                if line == "END:VEVENT":
                    break
                if not in_vevent:
                    continue

                if line.startswith("SUMMARY:"):
                    event.title = line[8:]
                elif line.startswith("DESCRIPTION:"):
                    event.description = line[12:]
                elif line.startswith("LOCATION:"):
                    event.location = line[9:]
                elif line.startswith("DTSTART"):
                    event.start_time = self._parse_ical_datetime(line)
                elif line.startswith("DTEND"):
                    event.end_time = self._parse_ical_datetime(line)
                elif line.startswith("UID:"):
                    event.email_uid = line[4:]
            return event
        except Exception:
            return None

    def _parse_ical_datetime(self, line: str) -> str:
        value = line.split(":", 1)[1] if ":" in line else ""
        value = value.strip()
        if "VALUE=DATE" in line:
            return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
        value = value.rstrip("Z")
        if len(value) >= 15:
            return f"{value[:4]}-{value[4:6]}-{value[6:8]}T{value[9:11]}:{value[11:13]}:{value[13:15]}"
        return value

    def _event_to_ical(self, event: CalendarEvent) -> str:
        dtstart = event.start_time.replace("-", "").replace(":", "").replace("T", "T")
        dtend = (
            event.end_time.replace("-", "").replace(":", "").replace("T", "T")
            if event.end_time
            else ""
        )
        return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//OpenEmail//EN
BEGIN:VEVENT
UID:{event.email_uid or f"openemail-{event.id}"}
SUMMARY:{event.title}
DESCRIPTION:{event.description}
LOCATION:{event.location}
DTSTART:{dtstart}
DTEND:{dtend}
END:VEVENT
END:VCALENDAR"""

    def _parse_sync_response(self, xml_text: str) -> tuple[list[dict], str]:
        changes = []
        new_token = ""
        try:
            root = ET.fromstring(xml_text)
            token_el = root.find("d:sync-token", CALDAV_NS)
            if token_el is not None:
                new_token = token_el.text or ""

            for response in root.findall(".//d:response", CALDAV_NS):
                href_el = response.find("d:href", CALDAV_NS)
                status_el = response.find("d:status", CALDAV_NS)
                if href_el is not None:
                    is_deleted = status_el is not None and "404" in (
                        status_el.text or ""
                    )
                    changes.append(
                        {
                            "url": href_el.text,
                            "deleted": is_deleted,
                        }
                    )
        except ET.ParseError:
            pass
        return changes, new_token

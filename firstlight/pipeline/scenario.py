"""Deterministic seed scenario for a representative NCR morning.

This is honest fixture data: realistic station/climate geometry that mirrors
a typical bad Delhi winter morning (big NW Punjab/Haryana stubble-fires,
elevated AQI in the south-east cells of the wind shadow). No live APIs are
required for the demo nor for the test suite.
"""

from __future__ import annotations

from ..domain import MorningInputs, School, Station, StubbleFire, Wind

DATE = "2026-10-08"
WIND = Wind(direction_deg=310.0, speed_kmh=16.0, observed_utc="2026-10-08T03:00:00Z")

STATIONS = (
    Station("st-anand-vihar", "Anand Vihar, Delhi", 28.6462, 77.3157, 427, "PM2.5", "2026-10-08T05:30:00Z"),
    Station("st-ito", "ITO, Delhi", 28.6304, 77.2427, 289, "PM2.5", "2026-10-08T05:30:00Z"),
    Station("st-pusa", "Pusa, Delhi", 28.6390, 77.1659, 318, "PM2.5", "2026-10-08T05:30:00Z"),
    Station("st-shadipur", "Shadipur, Delhi", 28.6512, 77.1505, 356, "PM2.5", "2026-10-08T05:30:00Z"),
    Station("st-dwarka", "Dwarka, Delhi", 28.5913, 77.0472, 402, "PM2.5", "2026-10-08T05:30:00Z"),
    Station("st-noida", "Noida, UP", 28.5744, 77.3221, 301, "PM2.5", "2026-10-08T05:30:00Z"),
    Station("st-gurugram", "Gurugram, Haryana", 28.4595, 77.0266, 264, "PM2.5", "2026-10-08T05:30:00Z"),
)

SCHOOLS = (
    School("s-avini", "Ramjas P. Block, Ashok Vihar", "Ashok Vihar", 28.6462, 77.3157, 820, True),
    School("s-guard", "GGSSS, ITO Crossing", "ITO", 28.6310, 77.2440, 1210, False),
    School("s-apj", "CPM Public School, Pusa Road", "Pusa", 28.6380, 77.1665, 540, True),
    School("s-spring", "Spring Meadow, Shadipur", "Shadipur", 28.6520, 77.1510, 460, True),
    School("s-dwarka", "DPS, Dwarka Sector 12", "Dwarka", 28.5900, 77.0490, 1180, False),
    School("s-noida", "Pearl Academy, Noida", "Noida Sector 62", 28.5750, 77.3230, 690, False),
    School("s-gurugram", "St. Andrews, Gurugram", "Sector 45", 28.4600, 77.0270, 760, False),
)

FIRES = (
    StubbleFire("f-ludh-1", 30.9010, 75.8573, "Ludhiana", "Punjab", 28.0, "2026-10-07T21:12:00Z", "active"),
    StubbleFire("f-mans-1", 29.9834, 75.3853, "Mansa", "Punjab", 22.0, "2026-10-07T22:05:00Z", "active"),
    StubbleFire("f-barn-1", 30.3794, 75.5487, "Barnala", "Punjab", 31.0, "2026-10-07T23:41:00Z", "active"),
    StubbleFire("f-sirsa-1", 29.5344, 75.0150, "Sirsa", "Haryana", 18.0, "2026-10-08T01:12:00Z", "active"),
    StubbleFire("f-fate-1", 29.5088, 75.4465, "Fatehabad", "Haryana", 14.0, "2026-10-08T02:10:00Z", "contained"),
    StubbleFire("f-sang-1", 30.2456, 75.8463, "Sangrur", "Punjab", 26.0, "2026-10-08T04:33:00Z", "active"),
    StubbleFire("f-food-1", 29.9994, 75.3927, "Faridkot", "Punjab", 12.0, "2026-10-08T03:41:00Z", "active"),
)

HISTORY: dict[str, list[int]] = {
    # 7 prior mornings: moderate-but-elevated baseline for the NCR winter
    "s-avini": [152, 160, 168, 175, 181, 189, 203],
    "s-guard": [121, 128, 135, 141, 149, 158, 167],
    "s-apj": [118, 125, 131, 138, 146, 154, 162],
    "s-spring": [131, 139, 146, 155, 166, 178, 190],
    "s-dwarka": [145, 153, 160, 169, 177, 186, 198],
    "s-noida": [110, 117, 124, 130, 138, 147, 156],
    "s-gurugram": [98, 104, 110, 116, 123, 131, 140],
}


def morning_inputs() -> MorningInputs:
    return MorningInputs(DATE, STATIONS, SCHOOLS, FIRES, WIND, HISTORY)

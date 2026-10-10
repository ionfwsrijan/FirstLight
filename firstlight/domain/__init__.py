"""Pure domain types. No imports from storage/engine; these are the nouns.

Coordinates are real NCR geography; the seeded scenario is representative.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Literal


class Level(IntEnum):
    GREEN = 0
    PROTECTED = 1
    CLOSED = 2

    @property
    def name_short(self) -> str:
        return self.name


class Trend(StrEnum):
    STABLE = "stable"
    RISING = "rising"
    COLLAPSING = "collapsing"
    IMPROVING = "improving"


@dataclass(frozen=True)
class Station:
    id: str
    name: str
    lat: float
    lon: float
    aqi: int
    main_pollutant: str
    last_updated_utc: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "lat": self.lat,
            "lon": self.lon,
            "aqi": self.aqi,
            "mainPollutant": self.main_pollutant,
            "lastUpdatedUtc": self.last_updated_utc,
        }


@dataclass(frozen=True)
class School:
    id: str
    name: str
    ward: str
    lat: float
    lon: float
    strength: int
    has_sensitive_group: bool
    opens_at: str = "08:30"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "ward": self.ward,
            "lat": self.lat,
            "lon": self.lon,
            "strength": self.strength,
            "hasSensitiveGroup": self.has_sensitive_group,
            "opensAt": self.opens_at,
        }


@dataclass(frozen=True)
class StubbleFire:
    id: str
    lat: float
    lon: float
    district: str
    state: str
    frp: float  # fire radiative power, MW (NASA FIRMS quantity)
    detected_utc: str
    status: Literal["active", "contained"]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "lat": self.lat,
            "lon": self.lon,
            "district": self.district,
            "state": self.state,
            "frp": self.frp,
            "detectedUtc": self.detected_utc,
            "status": self.status,
        }


@dataclass(frozen=True)
class Wind:
    direction_deg: float  # direction wind blows FROM (meteorological)
    speed_kmh: float
    observed_utc: str

    def to_dict(self) -> dict:
        return {
            "directionDeg": self.direction_deg,
            "speedKmh": self.speed_kmh,
            "observedUtc": self.observed_utc,
        }


@dataclass(frozen=True)
class MorningInputs:
    date: str  # iso date of the morning being decided
    stations: tuple[Station, ...]
    schools: tuple[School, ...]
    fires: tuple[StubbleFire, ...]
    wind: Wind
    history_aqi: dict[str, list[int]]  # school_id -> prior N morning AQIs

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "stations": [s.to_dict() for s in self.stations],
            "schools": [s.to_dict() for s in self.schools],
            "fires": [f.to_dict() for f in self.fires],
            "wind": self.wind.to_dict(),
            "historyAqi": self.history_aqi,
        }


@dataclass(frozen=True)
class RuleHit:
    rule_id: str
    title: str
    detail: str
    applied: bool
    value: object | None = None

    def to_dict(self) -> dict:
        return {
            "ruleId": self.rule_id,
            "title": self.title,
            "detail": self.detail,
            "applied": self.applied,
            "value": self.value,
        }


@dataclass(frozen=True)
class Decision:
    school_id: str
    date: str
    level: Level
    aqi_effective: float
    band_label: str
    band_hex: str
    grap_stage: int
    fires_upwind: int
    plume_score: float
    trend: str
    reasons: tuple[RuleHit, ...]
    actions: tuple[str, ...]
    evidence: dict

    def to_dict(self) -> dict:
        return {
            "schoolId": self.school_id,
            "date": self.date,
            "level": int(self.level),
            "levelName": self.level.name_short,
            "aqiEffective": round(self.aqi_effective, 1),
            "bandLabel": self.band_label,
            "bandHex": self.band_hex,
            "grapStage": self.grap_stage,
            "firesUpwind": self.fires_upwind,
            "plumeScore": round(self.plume_score, 3),
            "trend": self.trend,
            "reasons": [r.to_dict() for r in self.reasons],
            "actions": list(self.actions),
            "evidence": self.evidence,
        }

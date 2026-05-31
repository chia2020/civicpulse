from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Locality:
    zone: str
    latitude: float
    longitude: float
    population_density_score: float


LOCALITIES: dict[str, Locality] = {
    "ameerpet": Locality("Central", 17.4375, 78.4483, 8.4),
    "banjara hills": Locality("Central", 17.4126, 78.4482, 7.6),
    "khairatabad": Locality("Central", 17.4118, 78.4622, 8.0),
    "mehdipatnam": Locality("Central", 17.3949, 78.4398, 8.2),
    "mehdipatnam flyover": Locality("Central", 17.3949, 78.4398, 8.2),
    "tolichowki": Locality("Central", 17.3984, 78.4138, 7.8),
    "charminar": Locality("South", 17.3616, 78.4747, 9.0),
    "malakpet": Locality("South", 17.3736, 78.5150, 8.1),
    "falaknuma": Locality("South", 17.3301, 78.4675, 7.3),
    "kukatpally": Locality("West", 17.4933, 78.3995, 9.2),
    "kukatpally metro": Locality("West", 17.4933, 78.3995, 9.2),
    "gachibowli": Locality("West", 17.4401, 78.3489, 7.1),
    "madhapur": Locality("West", 17.4483, 78.3915, 8.0),
    "lb nagar": Locality("East", 17.3457, 78.5522, 8.5),
    "uppal": Locality("East", 17.4059, 78.5591, 8.1),
    "dilsukhnagar": Locality("East", 17.3687, 78.5247, 8.7),
    "secunderabad": Locality("Secunderabad", 17.4399, 78.4983, 9.0),
    "begumpet": Locality("Secunderabad", 17.4440, 78.4629, 8.4),
    "malkajgiri": Locality("North", 17.4474, 78.5265, 8.6),
    "alwal": Locality("North", 17.5047, 78.5033, 7.2),
}


UNKNOWN_LOCALITY = Locality("Unknown", 17.3850, 78.4867, 5.0)


def resolve_locality(text: str) -> Locality:
    normalized = text.lower().strip()
    for landmark, locality in LOCALITIES.items():
        if landmark in normalized:
            return locality
    return UNKNOWN_LOCALITY

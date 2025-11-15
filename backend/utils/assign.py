# backend/utils/assign.py
from math import radians, sin, cos, asin, sqrt
from datetime import datetime, timedelta
from typing import List, Tuple, Dict

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return 2 * R * asin(sqrt(a))

def week_bounds(dt: datetime) -> Tuple[datetime, datetime]:
    start = dt - timedelta(days=dt.weekday())
    start = datetime.combine(start.date(), datetime.min.time())
    end = start + timedelta(days=7) - timedelta(seconds=1)
    return start, end

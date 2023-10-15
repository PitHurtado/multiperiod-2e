"""Module for classes used in the application model."""
from typing import Dict, List, Optional


class Locatable:
    """Class for objects that have a location in the map."""

    def __init__(self, lon: float, lat: float):
        self.lon = lon
        self.lat = lat


class Pixel(Locatable):
    """Class for pixels in the map."""

    def __init__(
        self,
        id: str,
        lon: float,
        lat: float,
        area_km: float,
        customers_by_period: List[float],
        avg_drop: List[float],
        avg_stop: List[float],
        speed_intra_stop: Dict[str, float],
        k: float = 0.57,
    ):
        Locatable.__init__(self, lon, lat)
        self.id = id
        self.area_km = area_km
        self.customers_by_period = customers_by_period
        self.demand_by_period = []
        self.avg_drop = avg_drop
        self.avg_stop = avg_stop
        self.speed_intra_stop = speed_intra_stop
        self.k = k


class Satellite(Locatable):
    """Class for satellites in the map."""

    def __init__(
        self,
        id: str,
        lon: float,
        lat: float,
        distance_from_dc: float,
        duration_from_dc: Optional[float],
        duration_in_traffic_from_dic: Optional[float],
        cost_fixed: Dict[str, float],
        cost_operation: List[float],
        capacity: Dict[str, float],
        cost_sourcing: float,
    ):
        Locatable.__init__(self, lon, lat)
        self.id = id
        self.distance_from_dc = distance_from_dc
        self.duration_from_dc = duration_from_dc
        self.duration_in_traffic_from_dic = duration_in_traffic_from_dic
        self.cost_fixed = cost_fixed
        self.cost_operation = cost_operation
        self.cost_sourcing = 0.335 / 2  # TODO: Change this to a variable in the future
        self.capacity = capacity


class Vehicle:
    """Class for vehicles."""

    def __init__(
        self,
        id: str,
        type: str,
        capacity: float,
        cost_fixed: float,
        time_service: float,
        time_fixed: float,
        time_dispatch: float,
        time_load: float,
        speed_line_haul: float,
        max_time_services: float,
        k: float,
    ):
        self.id = str(id)
        self.type = type
        self.capacity = capacity
        self.cost_fixed = cost_fixed
        self.time_fixed = time_fixed
        self.time_service = time_service
        self.time_dispatch = time_dispatch
        self.time_load = time_load
        self.speed_line_haul = speed_line_haul
        self.max_time_services = max_time_services
        self.k = k

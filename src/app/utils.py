"""Module to define the configuration of the CA"""
import logging
import math
from abc import ABC, abstractmethod
from typing import Dict, Optional

from src.app.classes import Pixel, Satellite, Vehicle

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class CAConfig(ABC):
    """Abstract class to define the configuration of the CA"""

    def __init__(self, satellites: Dict[str, Satellite], periods: int) -> None:
        self.satellites = satellites
        self.periods = periods

    @abstractmethod
    def calculate_avg_fleet_size_from_satellites(
        self,
        pixels: Dict[str, Pixel],
        distances_line_haul: Dict[(str, str), float],
        **params
    ) -> Optional[Dict[(str, str, int), float]]:
        """Calculate the average fleet size for a pixel in a period of time"""
        pass

    @abstractmethod
    def calculate_avg_fleet_size_from_dc(
        self, pixels: Dict[str, Pixel], distances_line_haul: Dict[str, float], **params
    ) -> Dict[(str, int), float]:
        """Calculate the average fleet size for a pixel in a period of time"""
        pass


class CADeterministic(CAConfig):
    """Class to define the configuration of the CA"""

    def __init__(
        self,
        satellites: Dict[str, Satellite],
        periods: int,
        small_vehicle: Vehicle,
        large_vehicle: Vehicle,
    ) -> None:
        super().__init__(satellites, periods)
        self.small_vehicle = small_vehicle
        self.large_vehicle = large_vehicle

    def __avg_fleet_size(
        self, pixel: Pixel, vehicle: Vehicle, t: int, distance: float
    ) -> Dict[str, float]:
        """Calculate the average fleet size for a pixel in a period of time"""
        if (
            pixel.avg_drop[t] <= 0
            or pixel.avg_stop[t] <= 0
            or pixel.demand_by_period[t] <= 0
        ):
            return {
                "fleet_size": 0,
                "avg_tour_time": 0,
                "fully_loaded_tours": 0,
                "effective_capacity": 0,
                "demand_served": pixel.demand_by_period[t],
                "avg_drop": pixel.avg_drop[t],
                "avg_stop_density": pixel.avg_stop[t],
                "avg_time": 0,
                "avg_time_dispatch": 0,
                "avg_time_line_haul": 0,
            }

        # effective vehicle capacity
        effective_vehicle_capacity = vehicle.capacity / pixel.avg_drop[t]

        # time services
        time_services = vehicle.time_fixed + vehicle.time_service * pixel.avg_drop[t]

        # time intra stop
        time_intra_stop = (vehicle.k * pixel.k) / (
            pixel.speed_intra_stop[vehicle.type]
            * math.sqrt(pixel.avg_drop[t] / pixel.area_km)
        )

        # average tour time
        avg_tour_time = effective_vehicle_capacity * (time_services + time_intra_stop)

        # time preparing
        time_preparing_dispatch = (
            vehicle.time_dispatch
            + effective_vehicle_capacity * pixel.avg_drop[t] * vehicle.time_load
        )

        # time line_haul
        time_line_haul = 2 * (distance * vehicle.k / vehicle.speed_line_haul)

        # number of fully loaded tours
        beta = vehicle.Tmax / (avg_tour_time + time_preparing_dispatch + time_line_haul)
        avg_time = avg_tour_time + time_preparing_dispatch + time_line_haul

        # average fleet size
        numerador = pixel.avg_stop[t]
        denominador = beta * effective_vehicle_capacity
        v = (numerador / denominador) if denominador > 0 else 0.0

        return {
            "fleet_size": v,
            "avg_tour_time": avg_tour_time,
            "fully_loaded_tours": beta,
            "effective_capacity": effective_vehicle_capacity,
            "demand_served": pixel.demand_by_period[t],
            "avg_drop": pixel.avg_drop[t],
            "avg_stop_density": pixel.avg_stop[t],
            "avg_time": avg_time,
            "avg_time_dispatch": time_preparing_dispatch,
            "avg_time_line_haul": time_line_haul,
        }

    def calculate_avg_fleet_size_from_satellites(
        self,
        pixels: Dict[str, Pixel],
        distances_line_haul: Dict[(str, str), float],
        **params
    ) -> Optional[Dict[(str, str, int), float]]:
        """Calculate the average fleet size for a pixel in a period of time"""
        logger.info("[INFO] Estimation of fleet size running")
        fleet_size = dict(
            [
                (
                    (s.id, k.id, t),
                    self.__avg_fleet_size(
                        k, self.small_vehicle, t, distances_line_haul[(s.id, k.id)]
                    ),
                )
                for t in range(self.periods)
                for s in self.satellites
                for k in pixels.values()
            ]
        )
        logger.info("[INFO] Done")
        return fleet_size

    def calculate_avg_fleet_size_from_dc(
        self, pixels: Dict[str, Pixel], distances_line_haul: Dict[str, float], **params
    ) -> Dict[(str, int), float]:
        """Calculate the average fleet size for a pixel in a period of time"""
        logger.info("[INFO] Estimation of fleet size running")
        fleet_size = dict(
            [
                (
                    (k.id, t),
                    self.__avg_fleet_size(
                        k, self.large_vehicle, t, distances_line_haul[k.id]
                    ),
                )
                for t in range(self.periods)
                for k in pixels.values()
            ]
        )
        logger.info("[INFO] Done")
        return fleet_size

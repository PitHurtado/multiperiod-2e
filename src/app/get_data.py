"""Module to get data from csv file"""
import json
import logging
import os
import sys
from typing import Dict, Tuple

import pandas as pd

from src.app.classes import Pixel, Satellite
from src.app.constants import (
    DATA_DISTANCES_FROM_DC_PATH,
    DATA_DISTANCES_FROM_SATELLITES_PATH,
    DATA_PIXEL_PATH,
    DATA_SATELLITE_PATH,
    ROOT_SCENARIO_PATH,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Data:
    """Class to get data from csv file"""

    @staticmethod
    def load_satellites(
        show_data: bool = False,
    ) -> Tuple[Dict[str, Satellite], pd.DataFrame]:
        """Load data from csv file and create a dictionary of satellites"""
        satellites = {}
        if not os.path.isfile(DATA_SATELLITE_PATH):
            logging.error(f"[ERROR] File {DATA_SATELLITE_PATH} not found")
            sys.exit(1)
        logging.info(
            f"[INFO] loading data from satellites from path {DATA_SATELLITE_PATH}"
        )
        df = pd.read_csv(DATA_SATELLITE_PATH)
        logger.info(f"[INFO] Count of SATELLITES loaded: {len(df)}")
        for _, row in df.iterrows():
            # get the id of the satellite
            id = str(row["id_satellite"])
            # get the cost of operation
            cost_operation = json.loads(row["cost_operation"])
            # get the cost of sourcing
            cost_sourcing = row["cost_sourcing"]
            # get the capacity
            capacity = json.loads(row["capacity"])
            # create a new satellite
            new_satellite = Satellite(
                id=id,
                lon=row["lon"],
                lat=row["lat"],
                distance_from_dc=row["distance"],
                duration_from_dc=row["duration"],
                duration_in_traffic_from_dic=row["duration_in_traffic"],
                cost_fixed=json.loads(row["cost_fixed"]),
                cost_operation=cost_operation,
                cost_sourcing=cost_sourcing,
                capacity=capacity,
            )
            satellites[id] = new_satellite
        if show_data:
            for s in satellites.values():
                logger.info(
                    "-" * 50 + "\n" + json.dumps(s.__dict__, indent=2, default=str)
                )
        logging.info("[INFO] Loaded OK")
        return satellites, df

    @staticmethod
    def load_pixels(show_data: bool = False) -> Dict[str, Pixel]:
        """Load data from csv file and create a dictionary of pixels"""
        pixels = {}
        if not os.path.isfile(DATA_PIXEL_PATH):
            logging.error(f"[ERROR] File {DATA_PIXEL_PATH} not found")
            sys.exit(1)
        logging.info(f"[INFO] loading data from pixels from path {DATA_PIXEL_PATH}")
        df = pd.read_csv(DATA_PIXEL_PATH)
        # logger.info("[INFO] Sanity check of data")
        # filtered only rows with cajas > 0
        df.dropna(inplace=True)
        df.reset_index(drop=True, inplace=True)

        logger.info(f"[INFO] Count of PIXELS loaded: {len(df)}")
        for _, row in df.iterrows():
            id = str(row["id_pixel"])
            # get the customers by period
            customers_by_period = json.loads(row["avg_customers_by_period"])
            # get the demand by period
            demand_by_period = json.loads(row["avg_demand_by_period"])
            # get the avg drop
            drop_by_period = json.loads(row["avg_drop_by_period"])
            # get the avg stop
            stop_by_period = json.loads(row["avg_stop_by_period"])
            # get the speed intra stop
            speed_intra_stop = json.loads(row["speed_intra_stop"])
            # create a new pixel
            new_pixel = Pixel(
                id=id,
                lon=row["lon"],
                lat=row["lat"],
                area_km=row["area_km"],
                customers_by_period=customers_by_period,
                avg_drop=drop_by_period,
                avg_stop=stop_by_period,
                speed_intra_stop=speed_intra_stop,
            )
            pixels[id] = new_pixel

        logger.info("[INFO] Loaded OK")
        if show_data:
            for p in pixels.values():
                logger.info(
                    "-" * 50 + "\n" + json.dumps(p.__dict__, indent=2, default=str)
                )
        return pixels

    @staticmethod
    def load_matrix_from_satellite() -> Dict[str, Dict]:
        """Load data from csv file and create a dictionary of distances and durations"""
        if not os.path.isfile(DATA_DISTANCES_FROM_SATELLITES_PATH):
            logger.error(
                f"[ERROR] File {DATA_DISTANCES_FROM_SATELLITES_PATH} not found"
            )
            sys.exit(1)
        logger.info(
            f"[INFO] loading data of durations and distance path {DATA_DISTANCES_FROM_SATELLITES_PATH}"
        )
        df = pd.read_csv(DATA_DISTANCES_FROM_SATELLITES_PATH)

        # iterate through the dataframe and create a dictionary using dictionary comprehension
        distance = {
            (row["id_satellite"], row["id_cluster"]): row["distance"] / 1000
            for _, row in df.iterrows()
        }
        duration = {
            (row["id_satellite"], row["id_cluster"]): row["duration"] / 3600
            for _, row in df.iterrows()
        }
        duration_in_traffic = {
            (row["id_satellite"], row["id_cluster"]): row["duration_in_traffic"] / 3600
            for _, row in df.iterrows()
        }
        matrix = {
            "duration": duration,
            "distance": distance,
            "duration_in_traffic": duration_in_traffic,
        }
        logger.info("Loaded OK")
        return matrix

    @staticmethod
    def load_matrix_from_dc() -> Dict[str, Dict]:
        """Load data from csv file and create a dictionary of distances and durations"""
        if not os.path.isfile(DATA_DISTANCES_FROM_DC_PATH):
            logger.error(f"[ERROR] File {DATA_DISTANCES_FROM_DC_PATH} not found")
            sys.exit(1)
        logger.info(
            f"[INFO] loading data of durations and distance path {DATA_DISTANCES_FROM_DC_PATH}"
        )
        df = pd.read_csv(DATA_DISTANCES_FROM_DC_PATH)
        # iterate through the dataframe and create a dictionary using dictionary comprehension
        distance = {
            (row["id_satellite"], row["id_cluster"]): row["distance"] / 1000
            for _, row in df.iterrows()
        }
        duration = {
            (row["id_satellite"], row["id_cluster"]): row["duration"] / 3600
            for _, row in df.iterrows()
        }
        duration_in_traffic = {
            (row["id_satellite"], row["id_cluster"]): row["duration_in_traffic"] / 3600
            for _, row in df.iterrows()
        }
        matrix = {
            "duration": duration,
            "distance": distance,
            "duration_in_traffic": duration_in_traffic,
        }
        logger.info("Loaded OK")
        return matrix

    @staticmethod
    def load_scenario(
        id: int, show_data: bool = False
    ) -> Tuple[Dict[str, Pixel], pd.DataFrame]:
        """Load data from scenario from csv file and create a dictionary of pixels"""
        base_pixels = Data.load_pixels(show_data)
        scenario_path = ROOT_SCENARIO_PATH + f"scenario_{id}.csv"
        if not os.path.isdir(scenario_path):
            logger.error(f"[ERROR] File {scenario_path} not found")
            sys.exit(1)
        logger.info(f"[INFO] loading data from scenario from path {scenario_path}")
        # load pixels
        df = pd.read_csv(scenario_path)
        # logger.info("[INFO] Sanity check of data")
        # filtered only rows with cajas > 0
        df.dropna(inplace=True)
        df.reset_index(drop=True, inplace=True)
        logger.info(f"[INFO] Count of PIXELS loaded: {len(df)}")

        pixels = {}
        for _, row in df.iterrows():
            id = str(row["id_pixel"])
            # get the demand by period
            demand_by_period = json.loads(row["avg_demand_by_period"])
            # filter the base pixel
            pixel = base_pixels.get(id, None)
            if not pixel is None:
                # update the demand by period
                pixel.demand_by_period = demand_by_period
                # add the pixel to the dictionary
                pixels[id] = pixel
        logger.info("[INFO] Loaded OK")
        if show_data:
            for p in pixels.values():
                logger.info(
                    "-" * 50 + "\n" + json.dumps(p.__dict__, indent=2, default=str)
                )
        return pixels, df

"""Module of Grid Constructor"""
import logging

import geopandas as gpd
import numpy as np
import pandas as pd
from geopy.distance import geodesic
from shapely.geometry import Polygon

logger = logging.getLogger(__name__)


class GridCreator:
    """Class of Grid Constructor"""

    def __init__(
        self, df: pd.DataFrame, km_distance: int
    ):  # pylint: disable=invalid-name
        self.df_input = df
        self.km_distance = km_distance
        self.geo: pd.DataFrame = None  # type: ignore
        self.df_output: pd.DataFrame = None  # type: ignore

    def __calculate_delta_lat_lon(self, lat: float) -> tuple[float, float]:
        """Calculate of delta lat and lon"""
        delta_lat = (
            geodesic(kilometers=self.km_distance).destination((lat, 0), 0)[0] - lat
        )
        delta_lng = geodesic(kilometers=self.km_distance).destination((lat, 0), 90)[1]
        return delta_lat, delta_lng

    def create_grid(self) -> None:
        """Create a grid from DataFrame"""
        min_lat, max_lat = (
            self.df_input["lat"].min(),
            self.df_input["lat"].max(),
        )
        min_lng, max_lng = (
            self.df_input["lon"].min(),
            self.df_input["lon"].max(),
        )
        delta_lat, delta_lng = self.__calculate_delta_lat_lon(min_lat)

        num_rows = int(np.ceil((max_lat - min_lat) / delta_lat))
        num_cols = int(np.ceil((max_lng - min_lng) / delta_lng))

        grid_polygons = []
        for i in range(num_rows):
            for j in range(num_cols):
                top_left_lat = min_lat + i * delta_lat
                top_left_lng = min_lng + j * delta_lng

                # Polygon Coordinates for Cell
                polygon = Polygon(
                    [
                        (top_left_lng, top_left_lat),
                        (top_left_lng + delta_lng, top_left_lat),
                        (top_left_lng + delta_lng, top_left_lat - delta_lat),
                        (top_left_lng, top_left_lat - delta_lat),
                    ]
                )
                grid_polygons.append(polygon)

        gdf_grid = gpd.GeoDataFrame(geometry=grid_polygons, crs="EPSG:4326")  # type: ignore

        # Save as a GeoJson for storing the geo information of polygons
        # name = "..path.." + str(self.km_distance) + "km^2.geojson"
        # gdf_grid.to_file(name, driver="GeoJSON")
        if len(gdf_grid.index) > 0:
            self.geo = gdf_grid

    def combinate_output(self) -> None:
        """Combinate output with Grid"""
        # Step 1: Create a GeoDataFrame for the Original Data (df)
        gdf_orders = gpd.GeoDataFrame(
            self.df_input,
            geometry=gpd.points_from_xy(self.df_input["lon"], self.df_input["lat"]),
            crs="EPSG:4326",
        )  # type: ignore

        # Step 2: Join both gpds and create a new column to identify pixel
        # pylint: disable=logging-fstring-interpolation
        logger.info(f"[GRID-CREATOR] number of pixels: {len(self.geo)}")
        self.geo["cell_id"] = np.arange(len(self.geo))
        gdf_combined = gpd.sjoin(gdf_orders, self.geo, how="left", op="within")
        gdf_combined = gdf_combined.rename(columns={"cell_id": "pixel"})

        # Step 4: Drop unnecessary columns and convert back to a pandas dataframe
        df_combined = gdf_combined.drop(columns=["geometry", "index_right"]).copy()

        # Step 5: Save dataframe in a new Pixel
        # df_combined.to_csv("input_data/data_2015_gridification.csv")
        self.df_output = df_combined

    def run(self) -> pd.DataFrame:
        """Execute all steps for create Grid"""
        self.create_grid()
        self.combinate_output()
        return self.df_output

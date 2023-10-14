"""Module of Plot Grid"""
import logging

import geopandas as gpd
import pandas as pd
from matplotlib import pyplot as plt

logger = logging.getLogger(__name__)


class PlotGrid:
    """Class of plotting grid"""

    def __init__(
        self, grid_geo: gpd.GeoDataFrame, df: pd.DataFrame
    ) -> None:  # pylint: disable=invalid-name
        self.grid_geo: pd.DataFrame = grid_geo
        self.df_input: pd.DataFrame = df

    def plot_density_customer(self, figsize=(10, 10)) -> None:
        """Plot density of customer per pixel"""
        # Calculate size / density per pixel
        customer_density = (
            self.df_input.groupby("pixel").size().reset_index(name="cust_density")
        )

        # Join geo data with dataframe-density
        gdf_grid = self.grid_geo.merge(
            customer_density, left_index=True, right_on="pixel", how="left"
        ).fillna(0)
        # pylint: disable=logging-fstring-interpolation
        logger.info(f"[Plotting Grid] Total pixels: {len(gdf_grid.index)} \n")

        # Split the geopandas into two: one for zero order density
        # and another for positive order density
        gdf_zero_density = gdf_grid[gdf_grid["cust_density"] == 0].copy()
        gdf_positive_density = gdf_grid[gdf_grid["cust_density"] > 0].copy()

        gdf_low_density = gdf_grid[
            (gdf_grid["cust_density"] < 20) & (gdf_grid["cust_density"] > 0)
        ].copy()
        # pylint: disable=logging-fstring-interpolation
        logger.info(
            f"\n[Plotting Grid] Number of pixels w customers: {len(gdf_positive_density.index)} \n"
            f"[Plotting Grid] Number of pixels wo customers: {len(gdf_zero_density.index)} \n"
        )

        # Create the plot
        fig, ax = plt.subplots(figsize=figsize)

        # Plot the grid cells with zero order density (without fill color)
        gdf_zero_density.boundary.plot(ax=ax, linewidth=1, edgecolor="lightgrey")

        # Plot the grid cells with positive order density (with fill color)
        gdf_positive_density.plot(
            ax=ax,
            column="cust_density",
            cmap="Blues",  # o "YlGnBu"
            linewidth=1,
            edgecolor="lightgrey",
            legend=True,
        )

        gdf_low_density.plot(
            ax=ax,
            column="cust_density",
            color="orange",  # o "YlGnBu"
            linewidth=1,
            edgecolor="lightgrey",
            legend=True,
        )

        # Add labels to polygons
        for _, row in gdf_positive_density.iterrows():
            ax.annotate(
                text=row["cust_density"],
                xy=(row["geometry"].centroid.x, row["geometry"].centroid.y),
                xytext=(3, 3),
                textcoords="offset points",
                ha="center",
                fontsize=8,
            )

        ax.set_xlabel("Longitude", fontsize=14)
        ax.set_ylabel("Latitude", fontsize=14)
        ax.set_title("Customer Density per Pixel", fontsize=14)
        plt.show()

    def plot_grid_by_metric(self, metric: str, figsize=(10, 10)) -> None:
        """Plot grid with specific metric: mean, std, count, etc"""
        # Calculate std per pixel
        metric_per_pixel = self.df_input.groupby("pixel").agg(
            agg_metric=("demand", metric)
        )

        # Join geo data with dataframe-density
        gdf_grid = self.grid_geo.merge(
            metric_per_pixel, left_index=True, right_on="pixel", how="left"
        ).fillna(0)
        logger.info(f"[Plotting Grid] Total pixels: {len(gdf_grid.index)} \n")

        # Split the GeoDataFrame into two: one for zero order density and another for positive order density
        gdf_zero_density = gdf_grid[gdf_grid["agg_metric"] == 0].copy()
        gdf_positive_density = gdf_grid[gdf_grid["agg_metric"] > 0].copy()

        # Create the plot
        fig, ax = plt.subplots(figsize=figsize)

        # Plot the grid cells with zero order density (without fill color)
        gdf_zero_density.boundary.plot(ax=ax, linewidth=1, edgecolor="lightgrey")

        # Plot the grid cells with positive order density (with fill color)
        gdf_positive_density.plot(
            ax=ax,
            column="agg_metric",
            cmap="Purples",  # o "YlGnBu"
            linewidth=1,
            edgecolor="lightgrey",
            legend=True,
        )

        # Add labels to polygons
        for idx, row in gdf_positive_density.iterrows():
            annotation_text = "{:.1f}".format(
                row["agg_metric"]
            )  # Formato con un decimal
            ax.annotate(
                text=annotation_text,
                xy=(row["geometry"].centroid.x, row["geometry"].centroid.y),
                xytext=(3, 3),
                textcoords="offset points",
                ha="center",
                fontsize=8,
            )

        ax.set_xlabel("Longitude", fontsize=14)
        ax.set_ylabel("Latitude", fontsize=14)
        ax.set_title(f"{metric.upper()} per Pixel", fontsize=14)
        plt.show()

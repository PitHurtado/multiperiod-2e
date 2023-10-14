"""Model Multiperiod."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import gurobipy as gb
from gurobipy import GRB, quicksum

from src.app.classes import Pixel, Satellite


class ModelMultiperiod(ABC):
    """Model Multiperiod."""

    def __init__(self, NAME_MODEL: str) -> None:
        self.model = gb.Model(NAME_MODEL)

    def optimize_model(self) -> str:
        """Optimize the model."""
        self.model.optimize()
        return self.model.Status

    def show_model(self):
        """Show the model."""
        self.model.display()

    def set_params(self, params: Dict[str, int]):
        """Set params to model."""
        for key, item in params.items():
            self.model.setParam(key, item)

    @abstractmethod
    def get_results(
        self, satellites: List[Satellite], pixels: List[Pixel]
    ) -> Optional[Dict[str, Any]]:
        """Get results from model."""
        pass


class Deterministic(ModelMultiperiod):
    """
    Model Deterministic.
    """

    def __init__(self, periods: int, name_model="Deterministic-MultiPeriod"):
        super().__init__(NAME_MODEL=name_model)

        self.PERIODS = periods

        # variables
        self.X = {}
        self.Y = {}
        self.W = {}
        self.Z = {}

        # objetive & metrics
        self.results = {}
        self.metrics = {}

    def build(
        self,
        satellites: List[Satellite],
        pixels: List[Pixel],
        vehicles_required: Dict[str, Dict],
        costs: Dict[str, Dict],
    ) -> Dict[str, float]:
        """Build the model."""
        self.model.reset()

        # 1.  add variables
        self.__add_variables(satellites, pixels)

        # 2. add objective
        self.__add_objective(satellites, pixels, costs)

        # 3. add constraints
        self.__add_constraints(satellites, pixels, vehicles_required)

        # 4. update model
        self.model.update()
        return {"time_building": 1}

    def __add_variables(self, satellites: List[Satellite], pixels: List[Pixel]) -> None:
        """Add variables to model."""
        # 1. add variable X: binary variable to decide if a satellite is operating in a period
        self.X = dict(
            [
                (
                    (s.id, q_id, t),
                    self.model.addVar(vtype=GRB.BINARY, name=f"X_s{s.id}_t{t}"),
                )
                for s in satellites
                for q_id in s.capacity.keys()
                for t in range(self.PERIODS)
            ]
        )

        # 2. add variable Y: binary variable to decide if a satellite is used to serve a pixel
        self.Z = dict(
            [
                (
                    (s.id, k.id, t),
                    self.model.addVar(vtype=GRB.BINARY, name=f"Z_s{s.id}_k{k.id}_t{t}"),
                )
                for s in satellites
                for k in pixels
                for t in range(self.PERIODS)
            ]
        )

        # 3. add variable W: binary variable to decide if a pixel is served from dc
        self.W = dict(
            [
                ((k.id, t), self.model.addVar(vtype=GRB.BINARY, name=f"W_k{k.id}_t{t}"))
                for k in pixels
                for t in range(self.PERIODS)
            ]
        )

        # 4. add variable Y: binary variable to decide if a satellite is open or not
        self.Y = dict(
            [
                (
                    (s.id, q_id),
                    self.model.addVar(vtype=GRB.BINARY, name=f"Y_s{s.id}_q{q_id}"),
                )
                for s in satellites
                for q_id in s.capacity.keys()
            ]
        )

    def __add_objective(
        self, satellites: List[Satellite], clusters: List[Pixel], costs: Dict[str, Dict]
    ) -> None:
        """Add objective to model."""
        # 1. add cost allocation satellites
        cost_allocation_satellites = quicksum(
            [
                (s.cost_fixed[q_id]) * self.Y[(s.id, q_id)]
                for s in satellites
                for q_id in s.capacity.keys()
            ]
        )

        # 2. add cost operating satellites
        cost_operating_satellites = quicksum(
            [
                (s.cost_operation[q_id][t]) * self.X[(s.id, q_id, t)]
                for s in satellites
                for q_id in s.capacity.keys()
                for t in range(self.PERIODS)
            ]
        )

        # 3. add cost served from satellite
        cost_served_from_satellite = quicksum(
            [
                costs["satellite"][(s.id, k.id, t)]["total"] * self.Z[(s.id, k.id, t)]
                for s in satellites
                for k in clusters
                for t in range(self.PERIODS)
            ]
        )

        # 4. add cost served from dc
        cost_served_from_dc = quicksum(
            [
                costs["dc"][(k.id, t)]["total"] * self.W[(k.id, t)]
                for k in clusters
                for t in range(self.PERIODS)
            ]
        )

        cost_total = (
            cost_allocation_satellites
            + cost_served_from_dc
            + cost_served_from_satellite
            + cost_operating_satellites
        )
        self.model.setObjective(cost_total, GRB.MINIMIZE)

    def __add_constraints(
        self, satellites: List[Satellite], pixels: List[Pixel], vehicles_required: Dict
    ) -> None:
        """Add constraints to model."""
        pass

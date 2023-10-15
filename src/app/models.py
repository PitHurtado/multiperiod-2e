"""Model Multiperiod."""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import gurobipy as gb
from gurobipy import GRB, quicksum

from src.app.classes import Pixel, Satellite

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ModelMultiperiod(ABC):
    """Model Multiperiod."""

    def __init__(self, NAME_MODEL: str) -> None:
        self.model = gb.Model(NAME_MODEL)

    def optimize_model(self) -> str:
        """Optimize the model."""
        logger.info("[Run] Optimize model")
        self.model.optimize()
        logger.info(f"Status: {self.model.Status}")
        return self.model.Status

    @abstractmethod
    def build(
        self,
        satellites: List[Satellite],
        pixels: List[Pixel],
        vehicles_required: Dict[str, Dict],
        costs: Dict[str, Dict],
        **kwargs,
    ) -> Dict[str, float]:
        """Build the model."""
        pass

    def show_model(self):
        """Show the model."""
        self.model.display()

    def set_params(self, params: Dict[str, int]):
        """Set params to model."""
        logger.info(f"[Run] Set params to model {params}")
        for key, item in params.items():
            self.model.setParam(key, item)

    @abstractmethod
    def get_results(self) -> Optional[Dict[str, Any]]:
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
        **kwargs,
    ) -> Dict[str, float]:
        """Build the model."""
        logger.info("[Run] Build model")
        self.model.reset()

        # 1.  add variables
        self.__add_variables(satellites, pixels)

        # 2. add objective
        self.__add_objective(satellites, pixels, costs)

        # 3. add constraints
        self.__add_constraints(satellites, pixels, vehicles_required)

        # 4. update model
        self.model.update()
        logger.info("[Run] Model built")
        return {"time_building": 1}

    def __add_variables(self, satellites: List[Satellite], pixels: List[Pixel]) -> None:
        """Add variables to model."""
        # 1. add variable X: binary variable to decide if a satellite is operating in a period
        logger.info("[Variable] Add variable X")
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
        logger.info(f"Number of variables X: {len(self.X)}")
        # 2. add variable Y: binary variable to decide if a satellite is used to serve a pixel
        logger.info("[Variable] Add variable Y")
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
        logger.info(f"Number of variables Z: {len(self.Z)}")
        # 3. add variable W: binary variable to decide if a pixel is served from dc
        logger.info("[Variable] Add variable W")
        self.W = dict(
            [
                ((k.id, t), self.model.addVar(vtype=GRB.BINARY, name=f"W_k{k.id}_t{t}"))
                for k in pixels
                for t in range(self.PERIODS)
            ]
        )
        logger.info(f"Number of variables W: {len(self.W)}")
        # 4. add variable Y: binary variable to decide if a satellite is open or not
        logger.info("[Variable] Add variable Y")
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
        logger.info(f"Number of variables Y: {len(self.Y)}")

    def __add_objective(
        self, satellites: List[Satellite], pixels: List[Pixel], costs: Dict[str, Dict]
    ) -> None:
        """Add objective to model."""
        # 1. add cost allocation satellites
        logger.info("[Objective] Add objective")
        self.cost_allocation_satellites = quicksum(
            [
                (s.cost_fixed[q_id]) * self.Y[(s.id, q_id)]
                for s in satellites
                for q_id in s.capacity.keys()
            ]
        )

        # 2. add cost operating satellites
        self.cost_operating_satellites = quicksum(
            [
                (s.cost_operation[q_id][t]) * self.X[(s.id, q_id, t)]
                for s in satellites
                for q_id in s.capacity.keys()
                for t in range(self.PERIODS)
            ]
        )

        # 3. add cost served from satellite
        self.cost_served_from_satellite = quicksum(
            [
                costs["satellite"][(s.id, k.id, t)]["total"] * self.Z[(s.id, k.id, t)]
                for s in satellites
                for k in pixels
                for t in range(self.PERIODS)
            ]
        )

        # 4. add cost served from dc
        self.cost_served_from_dc = quicksum(
            [
                costs["dc"][(k.id, t)]["total"] * self.W[(k.id, t)]
                for k in pixels
                for t in range(self.PERIODS)
            ]
        )

        self.cost_total = (
            self.cost_allocation_satellites
            + self.cost_served_from_dc
            + self.cost_served_from_satellite
            + self.cost_operating_satellites
        )
        logger.info(f"Objective: \n{self.cost_total}")
        self.model.setObjective(self.cost_total, GRB.MINIMIZE)

    def __add_constraints(
        self, satellites: List[Satellite], pixels: List[Pixel], vehicles_required: Dict
    ) -> None:
        """Add constraints to model."""
        self.__add_constr_allocation_satellite(satellites)
        self.__add_constr_operating_satellite(satellites)
        self.__add_constr_assign_pixel_sallite(satellites, pixels)
        self.__add_constr_capacity_satellite(satellites, pixels, vehicles_required)
        self.__add_constr_demand_satified(satellites, pixels)

    def __add_constr_allocation_satellite(self, satellites: List[Satellite]) -> None:
        """Add constraint allocation satellite."""
        logger.info("[Constraint] Add constraint allocation satellite")
        for s in satellites:
            nameConstraint = f"R_Open_s{s.id}"
            logger.info(f"Add constraint: {nameConstraint}")
            self.model.addConstr(
                quicksum([self.Y[(s.id, q_id)] for q_id in s.capacity.keys()]) <= 1,
                name=nameConstraint,
            )

    def __add_constr_operating_satellite(self, satellites: List[Satellite]) -> None:
        """Add constraint operating satellite."""
        logger.info("[Constraint] Add constraint operating satellite")
        for t in range(self.PERIODS):
            for s in satellites:
                for q_id in s.capacity.keys():
                    nameConstraint = f"R_Operating_s{s.id}_q{q_id}_t{t}"
                    logger.info(f"Add constraint: {nameConstraint}")
                    self.model.addConstr(
                        self.X[(s.id, q_id, t)] <= self.Y[(s.id, q_id)],
                        name=nameConstraint,
                    )

    def __add_constr_assign_pixel_sallite(
        self, satellites: List[Satellite], pixels: List[Pixel]
    ) -> None:
        """Add constraint assign pixel to satellite."""
        logger.info("[Constraint] Add constraint assign pixel to satellite")
        for t in range(self.PERIODS):
            for k in pixels:
                for s in satellites:
                    nameConstratint = f"R_Assign_s{s.id}_k{k.id}_t{t}"
                    logger.info(f"Add constraint: {nameConstratint}")
                    self.model.addConstr(
                        self.Z[(s.id, k.id, t)]
                        - quicksum(
                            [self.X[(s.id, q_id, t)] for q_id in s.capacity.keys()]
                        )
                        <= 0,
                        name=nameConstratint,
                    )

    def __add_constr_capacity_satellite(
        self,
        satellites: List[Satellite],
        pixels: List[Pixel],
        vehicles_required: Dict[str, Dict],
    ) -> None:
        """Add constraint capacity satellite."""
        logger.info("[Constraint] Add constraint capacity satellite")
        for t in range(self.PERIODS):
            for s in satellites:
                nameConstraint = f"R_capacity_s{s.id}_t{t}"
                logger.info(f"Add constraint: {nameConstraint}")
                self.model.addConstr(
                    quicksum(
                        [
                            self.Z[(s.id, k.id, t)]
                            * vehicles_required["small"][(s.id, k.id, t)]["fleet_size"]
                            for k in pixels
                        ]
                    )
                    - quicksum(
                        [
                            self.Y[(s.id, q_id)] * s.capacity[q_id]
                            for q_id in s.capacity.keys()
                        ]
                    )
                    <= 0,
                    name=nameConstraint,
                )

    def __add_constr_demand_satified(
        self, satellites: List[Satellite], pixels: List[Pixel]
    ):
        """Add constraint demand satisfied."""
        logger.info("[Constraint] Add constraint demand satisfied")
        for t in range(self.PERIODS):
            for k in pixels:
                nameConstraint = f"R_demand_k{k.id}_t{t}"
                logger.info(f"Add constraint: {nameConstraint}")
                self.model.addConstr(
                    quicksum([self.Z[(s.id, k.id, t)] for s in satellites])
                    + quicksum([self.W[(k.id, t)]])
                    == 1,
                    name=nameConstraint,
                )

    def get_results(self) -> Optional[Dict[str, Any]]:
        """Get results from model."""
        logger.info("[Run] Get results")
        kpi_models = {}
        if self.model.Status == GRB.OPTIMAL or self.model.Status == GRB.TIME_LIMIT:
            # 1. get results
            kpi_models["objective"] = self.model.ObjVal
            logger.info(f"Objective: {kpi_models['objective']}")
            kpi_models["status"] = self.model.Status
            logger.info(f"Status: {kpi_models['status']}")
            kpi_models["time"] = self.model.Runtime
            logger.info(f"Time: {kpi_models['time']}")
            kpi_models["gap"] = self.model.MIPGap
            logger.info(f"Gap: {kpi_models['gap']}")
            kpi_models["n_variables"] = self.model.NumVars
            kpi_models["n_constraints"] = self.model.NumConstrs
            kpi_models["n_nodes"] = self.model.NodeCount
            kpi_models["n_iterations"] = self.model.IterCount
            kpi_models["n_solutions"] = self.model.SolCount
            kpi_models["n_obj_values"] = self.model.ObjNVal
            kpi_models["n_cuts"] = self.model.CutN
            kpi_models["n_branches"] = self.model.BranchN
            kpi_models["n_barriers"] = self.model.BarIterCount
            kpi_models["n_gomory_cuts"] = self.model.GomoryN
            kpi_models["n_mip_start"] = self.model.NumMIPStart
            kpi_models["n_lazy_constraints"] = self.model.Lazy
            kpi_models["n_user_cuts"] = self.model.UserCut
            kpi_models["n_var_branches"] = self.model.VarBranch
            kpi_models["n_var_up_branches"] = self.model.VarUp
            kpi_models["n_var_down_branches"] = self.model.VarDown
            kpi_models["n_impl_bound_cuts"] = self.model.ImplBd
            kpi_models["n_flow_covers"] = self.model.FlowCover
            kpi_models["n_mir_cuts"] = self.model.MIRCuts
            kpi_models["n_gub_cuts"] = self.model.GUBCover
            kpi_models["n_clique_cuts"] = self.model.CliqueCuts
            kpi_models["n_flow_paths"] = self.model.FlowPath
            kpi_models["n_mcf_cuts"] = self.model.MCFCuts
            kpi_models["n_zero_half_cuts"] = self.model.ZeroHalfCuts
            kpi_models["n_network_cuts"] = self.model.NetworkCuts
            kpi_models["n_submip_nodes"] = self.model.SubMIPNodes
            kpi_models["n_cut_passes"] = self.model.CutPasses
            kpi_models["n_gomory_passes"] = self.model.GomoryPasses
            self.metrics["model"] = kpi_models

            # 2. get objective values
            self.metrics[
                "cost_allocation_satellite"
            ] = self.cost_allocation_satellites.getValue()
            logger.info(
                f"Cost allocation satellite: {self.metrics['cost_allocation_satellite']}"
            )
            self.metrics[
                "cost_operating_satellite"
            ] = self.cost_operating_satellites.getValue()
            logger.info(
                f"Cost operating satellite: {self.metrics['cost_operating_satellite']}"
            )
            self.metrics[
                "cost_served_from_satellite"
            ] = self.cost_served_from_satellite.getValue()
            logger.info(
                f"Cost served from satellite: {self.metrics['cost_served_from_satellite']}"
            )
            self.metrics["cost_served_from_dc"] = self.cost_served_from_dc.getValue()
            logger.info(f"Cost served from dc: {self.metrics['cost_served_from_dc']}")
            self.metrics["cost_total"] = self.cost_total.getValue()
            logger.info(f"Cost total: {self.metrics['cost_total']}")

            # 3. get variables values
            self.results["X"] = {
                key: self.X[key].x for key in self.X.keys() if self.X[key].x > 0
            }
            self.results["Y"] = {
                key: self.Y[key].x for key in self.Y.keys() if self.Y[key].x > 0
            }
            self.results["Z"] = {
                key: self.Z[key].x for key in self.Z.keys() if self.Z[key].x > 0
            }
            self.results["W"] = {
                key: self.W[key].x for key in self.W.keys() if self.W[key].x > 0
            }

            # 4. get constraints values
            self.metrics["constraints"] = {}
            self.metrics["constraints"]["allocation_satellite"] = {
                key: self.model.getConstrByName(key).slack
                for key in self.model.getConstrs()
                if "R_Open" in key.getAttr("ConstrName")
            }
            self.metrics["constraints"]["operating_satellite"] = {
                key: self.model.getConstrByName(key).slack
                for key in self.model.getConstrs()
                if "R_Operating" in key.getAttr("ConstrName")
            }
            self.metrics["constraints"]["assign_pixel_satellite"] = {
                key: self.model.getConstrByName(key).slack
                for key in self.model.getConstrs()
                if "R_Assign" in key.getAttr("ConstrName")
            }
            self.metrics["constraints"]["capacity_satellite"] = {
                key: self.model.getConstrByName(key).slack
                for key in self.model.getConstrs()
                if "R_capacity" in key.getAttr("ConstrName")
            }
            self.metrics["constraints"]["demand_satified"] = {
                key: self.model.getConstrByName(key).slack
                for key in self.model.getConstrs()
                if "R_demand" in key.getAttr("ConstrName")
            }
            logger.info("[Run] Results obtained")
        else:
            logger.info("[Run] Results not obtained")


class SecondStage(ModelMultiperiod):
    """Model Second Stage."""

    def __init__(
        self, periods: int, param_y: Dict, name_model="SecondStage-MultiPeriod"
    ):
        super().__init__(NAME_MODEL=name_model)

        self.PERIODS = periods

        # variables
        self.X = {}
        self.Y = param_y
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
        **kwargs,
    ) -> Dict[str, float]:
        """Build the model."""
        logger.info("[Run] Build model")
        self.model.reset()

        # 1.  add variables
        self.__add_variables(satellites, pixels)

        # 2. add objective
        self.__add_objective(satellites, pixels, costs)

        # 3. add constraints
        self.__add_constraints(satellites, pixels, vehicles_required)

        # 4. update model
        self.model.update()
        logger.info("[Run] Model built")
        return {"time_building": 1}

    def __add_variables(self, satellites: List[Satellite], pixels: List[Pixel]) -> None:
        """Add variables to model."""
        # 1. add variable X: binary variable to decide if a satellite is operating in a period
        logger.info("[Variable] Add variable X")
        self.X = dict(
            [
                (
                    (s.id, q_id, t),
                    self.model.addVar(vtype=GRB.BINARY, name=f"X_s{s.id}_t{t}"),
                )
                for s in satellites
                for q_id in s.capacity.keys()
                for t in range(self.PERIODS)
                if self.Y[(s.id, q_id)] > 0
            ]
        )
        logger.info(f"Number of variables X: {len(self.X)}")
        # 2. add variable Y: binary variable to decide if a satellite is used to serve a pixel
        logger.info("[Variable] Add variable Z")
        self.Z = dict(
            [
                (
                    (s.id, k.id, t),
                    self.model.addVar(vtype=GRB.BINARY, name=f"Z_s{s.id}_k{k.id}_t{t}"),
                )
                for s in satellites
                for k in pixels
                for t in range(self.PERIODS)
                if sum([self.Y[(s.id, q_id)] for q_id in s.capacity.keys()]) > 0
            ]
        )
        logger.info(f"Number of variables Z: {len(self.Z)}")
        # 3. add variable W: binary variable to decide if a pixel is served from dc
        logger.info("[Variable] Add variable W")
        self.W = dict(
            [
                ((k.id, t), self.model.addVar(vtype=GRB.BINARY, name=f"W_k{k.id}_t{t}"))
                for k in pixels
                for t in range(self.PERIODS)
            ]
        )
        logger.info(f"Number of variables W: {len(self.W)}")

    def __add_objective(
        self, satellites: List[Satellite], pixels: List[Pixel], costs: Dict[str, Dict]
    ) -> None:
        """Add objective to model."""
        # 1. add cost operating satellites
        logger.info("[Objective] Add objective")
        self.cost_allocation_satellites = sum(
            [
                (s.cost_fixed[q_id]) * self.Y[(s.id, q_id)]
                for s in satellites
                for q_id in s.capacity.keys()
                if self.Y[(s.id, q_id)] > 0
            ]
        )  # TODO verify if this is correct
        self.cost_operating_satellites = quicksum(
            [
                (s.cost_operation[q_id][t]) * self.X[(s.id, q_id, t)]
                for s in satellites
                for q_id in s.capacity.keys()
                for t in range(self.PERIODS)
                if self.Y[(s.id, q_id)] > 0
            ]
        )

        # 2. add cost served from satellite
        self.cost_served_from_satellite = quicksum(
            [
                costs["satellite"][(s.id, k.id, t)]["total"] * self.Z[(s.id, k.id, t)]
                for s in satellites
                for k in pixels
                for t in range(self.PERIODS)
                if sum([self.Y[(s.id, q_id)] for q_id in s.capacity.keys()]) > 0
            ]
        )

        # 3. add cost served from dc
        self.cost_served_from_dc = quicksum(
            [
                costs["dc"][(k.id, t)]["total"] * self.W[(k.id, t)]
                for k in pixels
                for t in range(self.PERIODS)
            ]
        )

        self.cost_total = (
            self.cost_served_from_dc
            + self.cost_served_from_satellite
            + self.cost_operating_satellites
        )
        logger.info(f"Objective: \n{self.cost_total}")
        self.model.setObjective(self.cost_total, GRB.MINIMIZE)

    def __add_constraints(
        self, satellites: List[Satellite], pixels: List[Pixel], vehicles_required: Dict
    ) -> None:
        """Add constraints to model."""
        self.__add_constr_assign_pixel_sallite(satellites, pixels)
        self.__add_constr_demand_satified(satellites, pixels)
        self.__add_constr_capacity_satellite(satellites, pixels, vehicles_required)

    def __add_constr_assign_pixel_sallite(
        self, satellites: List[Satellite], pixels: List[Pixel]
    ) -> None:
        """Add constraint assign pixel to satellite."""
        logger.info("[Constraint] Add constraint assign pixel to satellite")
        for t in range(self.PERIODS):
            for k in pixels:
                for s in satellites:
                    if sum([self.Y[(s.id, q_id)] for q_id in s.capacity.keys()]) > 0:
                        nameConstratint = f"R_Assign_s{s.id}_k{k.id}_t{t}"
                        logger.info(f"Add constraint: {nameConstratint}")
                        self.model.addConstr(
                            self.Z[(s.id, k.id, t)]
                            - quicksum(
                                [
                                    self.X[(s.id, q_id, t)]
                                    for q_id in s.capacity.keys()
                                    if self.Y[(s.id, q_id)] > 0
                                ]
                            )
                            <= 0,
                            name=nameConstratint,
                        )

    def __add_constr_demand_satified(
        self, satellites: List[Satellite], pixels: List[Pixel]
    ) -> None:
        """Add constraint demand satisfied."""
        logger.info("[Constraint] Add constraint demand satisfied")
        for t in range(self.PERIODS):
            for k in pixels:
                nameConstraint = f"R_demand_k{k.id}_t{t}"
                logger.info(f"Add constraint: {nameConstraint}")
                self.model.addConstr(
                    quicksum(
                        [
                            self.Z[(s.id, k.id, t)]
                            for s in satellites
                            if sum([self.Y[(s.id, q_id)] for q_id in s.capacity.keys()])
                            > 0
                        ]
                    )
                    + quicksum([self.W[(k.id, t)]])
                    == 1,
                    name=nameConstraint,
                )

    def __add_constr_capacity_satellite(
        self,
        satellites: List[Satellite],
        pixels: List[Pixel],
        vehicles_required: Dict[str, Dict],
    ) -> None:
        """Add constraint capacity satellite."""
        logger.info("[Constraint] Add constraint capacity satellite")
        for t in range(self.PERIODS):
            for s in satellites:
                if sum([self.Y[(s.id, q_id)] for q_id in s.capacity.keys()]) > 0:
                    nameConstraint = f"R_capacity_s{s.id}_t{t}"
                    logger.info(f"Add constraint: {nameConstraint}")
                    self.model.addConstr(
                        quicksum(
                            [
                                self.Z[(s.id, k.id, t)]
                                * vehicles_required["small"][(s.id, k.id, t)][
                                    "fleet_size"
                                ]
                                for k in pixels
                                if sum(
                                    [self.Y[(s.id, q_id)] for q_id in s.capacity.keys()]
                                )
                                > 0
                            ]
                        )
                        <= sum(
                            [
                                self.Y[(s.id, q_id)] * s.capacity[q_id]
                                for q_id in s.capacity.keys()
                                if self.Y[(s.id, q_id)] > 0
                            ]
                        ),
                        name=nameConstraint,
                    )

    def get_results(self) -> Optional[Dict[str, Any]]:
        """Get results from model."""
        logger.info("[Run] Get results")
        kpi_models = {}
        if self.model.Status == GRB.OPTIMAL or self.model.Status == GRB.TIME_LIMIT:
            # 1. get results
            kpi_models["objective"] = self.model.ObjVal
            logger.info(f"Objective: {kpi_models['objective']}")
            kpi_models["status"] = self.model.Status
            logger.info(f"Status: {kpi_models['status']}")
            kpi_models["time"] = self.model.Runtime
            logger.info(f"Time: {kpi_models['time']}")
            kpi_models["gap"] = self.model.MIPGap
            logger.info(f"Gap: {kpi_models['gap']}")
            kpi_models["n_variables"] = self.model.NumVars
            kpi_models["n_constraints"] = self.model.NumConstrs
            kpi_models["n_nodes"] = self.model.NodeCount
            kpi_models["n_iterations"] = self.model.IterCount
            kpi_models["n_solutions"] = self.model.SolCount
            kpi_models["n_obj_values"] = self.model.ObjNVal
            kpi_models["n_cuts"] = self.model.CutN
            kpi_models["n_branches"] = self.model.BranchN
            kpi_models["n_barriers"] = self.model.BarIterCount
            kpi_models["n_gomory_cuts"] = self.model.GomoryN
            kpi_models["n_mip_start"] = self.model.NumMIPStart
            kpi_models["n_lazy_constraints"] = self.model.Lazy
            kpi_models["n_user_cuts"] = self.model.UserCut
            kpi_models["n_var_branches"] = self.model.VarBranch
            kpi_models["n_var_up_branches"] = self.model.VarUp
            kpi_models["n_var_down_branches"] = self.model.VarDown
            kpi_models["n_impl_bound_cuts"] = self.model.ImplBd
            kpi_models["n_flow_covers"] = self.model.FlowCover
            kpi_models["n_mir_cuts"] = self.model.MIRCuts
            kpi_models["n_gub_cuts"] = self.model.GUBCover
            kpi_models["n_clique_cuts"] = self.model.CliqueCuts
            kpi_models["n_flow_paths"] = self.model.FlowPath
            kpi_models["n_mcf_cuts"] = self.model.MCFCuts
            kpi_models["n_zero_half_cuts"] = self.model.ZeroHalfCuts
            kpi_models["n_network_cuts"] = self.model.NetworkCuts
            kpi_models["n_submip_nodes"] = self.model.SubMIPNodes
            kpi_models["n_cut_passes"] = self.model.CutPasses
            kpi_models["n_gomory_passes"] = self.model.GomoryPasses
            self.metrics["model"] = kpi_models

            # 2. get objective values
            self.metrics["cost_allocation_satellite"] = self.cost_allocation_satellites
            logger.info(
                f"Cost allocation satellite: {self.metrics['cost_allocation_satellite']}"
            )
            self.metrics[
                "cost_operating_satellite"
            ] = self.cost_operating_satellites.getValue()
            logger.info(
                f"Cost operating satellite: {self.metrics['cost_operating_satellite']}"
            )
            self.metrics[
                "cost_served_from_satellite"
            ] = self.cost_served_from_satellite.getValue()
            logger.info(
                f"Cost served from satellite: {self.metrics['cost_served_from_satellite']}"
            )
            self.metrics["cost_served_from_dc"] = self.cost_served_from_dc.getValue()
            logger.info(f"Cost served from dc: {self.metrics['cost_served_from_dc']}")
            self.metrics["cost_total"] = self.cost_total.getValue()
            logger.info(f"Cost total: {self.metrics['cost_total']}")

            # 3. get variables values
            self.results["X"] = {
                key: self.X[key].x for key in self.X.keys() if self.X[key].x > 0
            }
            self.results["Y"] = {
                key: self.Y[key] for key in self.Y.keys() if self.Y[key] > 0
            }
            self.results["Z"] = {
                key: self.Z[key].x for key in self.Z.keys() if self.Z[key].x > 0
            }
            self.results["W"] = {
                key: self.W[key].x for key in self.W.keys() if self.W[key].x > 0
            }

            # 4. get constraints values
            self.metrics["constraints"] = {}
            self.metrics["constraints"]["assign_pixel_satellite"] = {
                key: self.model.getConstrByName(key).slack
                for key in self.model.getConstrs()
                if "R_Assign" in key.getAttr("ConstrName")
            }
            self.metrics["constraints"]["capacity_satellite"] = {
                key: self.model.getConstrByName(key).slack
                for key in self.model.getConstrs()
                if "R_capacity" in key.getAttr("ConstrName")
            }
            self.metrics["constraints"]["demand_satified"] = {
                key: self.model.getConstrByName(key).slack
                for key in self.model.getConstrs()
                if "R_demand" in key.getAttr("ConstrName")
            }
            logger.info("[Run] Results obtained")
        else:
            logger.info("[Run] Results not obtained")

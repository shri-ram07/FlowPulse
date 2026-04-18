r"""Default 40k-seat stadium topology used by the demo.

Spatial layout (SVG viewBox 0..1000 x 0..1000), arranged as concentric rings
so zones never overlap:

    Outer ring  : 7 entry gates + the exit ramp            (r ≈ 420)
    Ring 2      : restrooms, food courts, merch            (outer services)
    Ring 3      : 4 concourses (N, S, E, W)                (circulation)
    Ring 4      : 4 seating sectors (N, S, E, W)           (bowl)
    Centre      : pitch                                    (500, 500)

Edges (neighbors) are declared explicitly below so the frontend can render
them as connecting paths with flowing particles.
"""

from __future__ import annotations

from typing import cast

from backend.core.zone import Edge, Zone, ZoneKind


def default_stadium() -> list[Zone]:
    """Build and return the default 40k-seat stadium zone list."""

    def z(id_: str, name: str, kind: str, cap: int, x: float, y: float, neigh: list[tuple[str, int]]) -> Zone:
        return Zone(
            id=id_,
            name=name,
            kind=cast(ZoneKind, kind),
            capacity=cap,
            x=x,
            y=y,
            neighbors=[Edge(to=t, walk_seconds=s) for t, s in neigh],
        )

    zones = [
        # --- GATES (outer perimeter) -------------------------------------
        z("gate_a", "Gate A", "gate", 800, 200, 200, [("con_n", 40), ("con_w", 50)]),
        z("gate_b", "Gate B", "gate", 900, 420, 85, [("con_n", 30)]),
        z("gate_c", "Gate C", "gate", 900, 580, 85, [("con_n", 30)]),
        z("gate_d", "Gate D", "gate", 800, 800, 200, [("con_n", 40), ("con_e", 50)]),
        z("gate_e", "Gate E", "gate", 800, 200, 800, [("con_s", 40), ("con_w", 50)]),
        z("gate_f", "Gate F", "gate", 900, 500, 945, [("con_s", 30)]),
        z("gate_g", "Gate G", "gate", 800, 800, 800, [("con_s", 40), ("con_e", 50)]),
        # --- EXIT ramp ---------------------------------------------------
        z("exit_ramp", "Exit Ramp", "exit", 2000, 500, 855, [("con_s", 25), ("gate_f", 20)]),
        # --- CONCOURSES (4 cardinal rings) -------------------------------
        z(
            "con_n",
            "North Concourse",
            "concourse",
            3000,
            500,
            250,
            [
                ("gate_a", 40),
                ("gate_b", 30),
                ("gate_c", 30),
                ("gate_d", 40),
                ("food_1", 25),
                ("food_2", 25),
                ("con_w", 60),
                ("con_e", 60),
                ("seat_n", 20),
            ],
        ),
        z(
            "con_s",
            "South Concourse",
            "concourse",
            3000,
            500,
            750,
            [
                ("gate_e", 40),
                ("gate_f", 30),
                ("gate_g", 40),
                ("food_5", 25),
                ("food_6", 25),
                ("con_w", 60),
                ("con_e", 60),
                ("seat_s", 20),
                ("exit_ramp", 25),
            ],
        ),
        z(
            "con_w",
            "West Concourse",
            "concourse",
            2500,
            125,
            500,
            [
                ("con_n", 60),
                ("con_s", 60),
                ("food_3", 25),
                ("rest_1", 20),
                ("rest_2", 20),
                ("rest_3", 20),
                ("seat_w", 20),
            ],
        ),
        z(
            "con_e",
            "East Concourse",
            "concourse",
            2500,
            875,
            500,
            [
                ("con_n", 60),
                ("con_s", 60),
                ("food_4", 25),
                ("rest_4", 20),
                ("rest_5", 20),
                ("rest_6", 20),
                ("seat_e", 20),
                ("merch_1", 30),
            ],
        ),
        # --- FOOD courts (between concourses & outer ring) ---------------
        z("food_1", "Food Court 1", "food", 180, 340, 155, [("con_n", 25)]),
        z("food_2", "Food Court 2", "food", 180, 660, 155, [("con_n", 25)]),
        z("food_3", "Food Court 3", "food", 150, 65, 380, [("con_w", 25)]),
        z("food_4", "Food Court 4", "food", 150, 935, 380, [("con_e", 25)]),
        z("food_5", "Food Court 5", "food", 180, 340, 845, [("con_s", 25)]),
        z("food_6", "Food Court 6", "food", 180, 660, 845, [("con_s", 25)]),
        # --- RESTROOMS (side columns) ------------------------------------
        z("rest_1", "Restroom W-1", "restroom", 60, 65, 230, [("con_w", 20)]),
        z("rest_2", "Restroom W-2", "restroom", 60, 65, 500, [("con_w", 20)]),
        z("rest_3", "Restroom W-3", "restroom", 60, 65, 770, [("con_w", 20)]),
        z("rest_4", "Restroom E-1", "restroom", 60, 935, 230, [("con_e", 20)]),
        z("rest_5", "Restroom E-2", "restroom", 60, 935, 500, [("con_e", 20)]),
        z("rest_6", "Restroom E-3", "restroom", 60, 935, 770, [("con_e", 20)]),
        # --- SEATING (ring just around pitch) ----------------------------
        z("seat_n", "Seating North", "seating", 10000, 500, 335, [("con_n", 20)]),
        z("seat_s", "Seating South", "seating", 10000, 500, 665, [("con_s", 20)]),
        z("seat_w", "Seating West", "seating", 10000, 245, 500, [("con_w", 20)]),
        z("seat_e", "Seating East", "seating", 10000, 755, 500, [("con_e", 20)]),
        # --- MERCH (single kiosk) ----------------------------------------
        z("merch_1", "Merch Store", "merch", 120, 820, 175, [("con_e", 30), ("gate_d", 25)]),
    ]
    return zones

"""
STEP 1 - Compute, once and for all, how strong the wake is for each wind
direction, for every park, with FLORIS.

For each park, FLORIS is run on its YAML (layout, turbines and wake model as
defined there) for the 360 wind directions, at one reference wind speed.
For each direction:

  wake_loss = 1 - farm power with wakes / farm power without wakes
  waked_turbines_frac = share of turbines losing more than TURBINE_LOSS_MIN
  wake = True if wake_loss >= WAKE_LOSS_THRESHOLD

This takes a few seconds per park. Your prediction data is not used here.

What you need before running:
  1. One FLORIS v4 YAML per park. Start from park_example.yaml (every field
     is commented there) and edit, for each park:
       farm.layout_x / layout_y  turbine positions in metres, x = east,
                                 y = north (any origin, but y MUST point north,
                                 otherwise every wake direction is rotated)
       farm.turbine_type         nrel_5MW, iea_10MW, iea_15MW, iea_22MW, or your
                                 own turbine file (see turbine_library_path in
                                 the template). Pick the closest rotor
                                 diameter: wake distances scale with it.
     Wind directions, wind speeds and turbulence intensities written in the
     YAML are ignored: they are replaced by the 360 directions and by
     REF_WIND_SPEED / TURBULENCE_INTENSITY below.
     The wake section can stay as in the template (Gauss-Curl Hybrid).
  2. List the parks in PARKS below: {"park name": "path/to/park.yaml"}.
     Use the same park names in 2_analyse_predictions.py.
  3. Check that FLORIS reads a YAML:
       python -c "from floris import FlorisModel; print(FlorisModel('park_A.yaml').n_turbines)"
  4. Run from the folder containing the YAMLs:  python 1_wake_directions.py

Output:
  out/wake_directions.csv   park, wind_direction, wake_loss, waked_turbines_frac, wake
  out/<park>_wake_rose.png  wake loss vs wind direction
  out/<park>_layout.png     layout with the lines along which turbines wake each other
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from floris import FlorisModel
from floris import layout_visualization as layoutviz

# ============================ CONFIGURATION ============================
# >>> EDIT: one entry per park, "name": "FLORIS YAML" (template: park_example.yaml)
# Paths are relative to the folder you run the script from.
PARKS = {
    "park_A": "park_A.yaml",
    # "park_B": "park_B.yaml",
}

REF_WIND_SPEED = 8.0         # m/s, below rated: where wakes cost the most
TURBULENCE_INTENSITY = 0.06  # ~0.06 offshore, 0.08-0.12 onshore; higher = shorter wakes
WAKE_LOSS_THRESHOLD = 0.05   # farm loss >= 5% -> wake direction
TURBINE_LOSS_MIN = 0.05      # a turbine counts as "waked" if it loses > 5%
LAYOUT_PLOT_MAX_DIST_D = 10  # on the layout plot, only show wake lines up to 10 D
OUT_DIR = Path("out")
# =======================================================================


def wake_by_direction(yaml_path):
    fmodel = FlorisModel(yaml_path)

    directions = np.arange(360.0)
    fmodel.set(wind_directions=directions,
               wind_speeds=np.full(360, REF_WIND_SPEED),
               turbulence_intensities=np.full(360, TURBULENCE_INTENSITY))

    fmodel.run()
    p_wake = fmodel.get_turbine_powers()          # shape (360, turbines)
    fmodel.run_no_wake()
    p_free = fmodel.get_turbine_powers()

    farm_loss = 1 - p_wake.sum(axis=1) / p_free.sum(axis=1)
    turb_loss = 1 - p_wake / np.where(p_free > 0, p_free, np.nan)
    waked_frac = (turb_loss > TURBINE_LOSS_MIN).mean(axis=1)

    return fmodel, directions.astype(int), farm_loss, waked_frac


def plot_wake_rose(loss, park, out):
    theta = np.deg2rad(np.arange(361))
    r = np.append(loss, loss[0]) * 100
    fig = plt.figure(figsize=(5, 5))
    ax = fig.add_subplot(projection="polar")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)          # compass: clockwise, N on top
    ax.plot(theta, r, color="#d64545")
    ax.fill(theta, r, color="#d64545", alpha=0.25)
    ax.plot(theta, np.full_like(theta, WAKE_LOSS_THRESHOLD * 100), "k--", lw=0.8)
    ax.set_title(f"{park}: farm wake loss (%) at {REF_WIND_SPEED:g} m/s\nvs wind direction (from)", pad=15)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def plot_layout(fmodel, park, out):
    fig, ax = plt.subplots(figsize=(7, 7))
    layoutviz.plot_turbine_points(fmodel, ax=ax)
    layoutviz.plot_turbine_labels(fmodel, ax=ax)
    layoutviz.plot_waking_directions(fmodel, ax=ax, limit_dist_D=LAYOUT_PLOT_MAX_DIST_D)
    ax.set_title(f"{park}: layout and waking directions (≤ {LAYOUT_PLOT_MAX_DIST_D} D)")
    ax.set_xlabel("x (m, east)")
    ax.set_ylabel("y (m, north)")
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def main():
    OUT_DIR.mkdir(exist_ok=True)
    rows = []
    for park, yaml_path in PARKS.items():
        fmodel, directions, loss, waked_frac = wake_by_direction(yaml_path)
        rows.append(pd.DataFrame({
            "park": park,
            "wind_direction": directions,
            "wake_loss": loss.round(4),
            "waked_turbines_frac": waked_frac.round(3),
            "wake": loss >= WAKE_LOSS_THRESHOLD,
        }))
        plot_wake_rose(loss, park, OUT_DIR / f"{park}_wake_rose.png")
        plot_layout(fmodel, park, OUT_DIR / f"{park}_layout.png")
        print(f"{park}: {fmodel.n_turbines} turbines, "
              f"max wake loss {loss.max():.1%} at {directions[loss.argmax()]}°, "
              f"{(loss >= WAKE_LOSS_THRESHOLD).sum()} wake directions out of 360")

    pd.concat(rows).to_csv(OUT_DIR / "wake_directions.csv", index=False)
    print(f"Saved {OUT_DIR / 'wake_directions.csv'}")


if __name__ == "__main__":
    main()

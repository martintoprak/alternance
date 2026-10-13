# Wake-direction analysis of wind power predictions

Two scripts to check whether power predictions are worse when turbines sit in each other's wake.

1. **`1_wake_directions.py`**: runs [FLORIS](https://github.com/NREL/floris) on each park's layout for the 360 wind directions. For each direction it computes the farm wake loss and labels it `wake` / `no_wake`.
2. **`2_analyse_predictions.py`**: labels every time step of your predictions as `wake` / `no_wake` from its wind direction. It then compares errors (bias, MAE, RMSE) between the two groups **at the same wind speed**.

## Installation

```bash
pip install -r requirements.txt
```

The scripts need FLORIS 4 or later (tested with 4.6).

## What you need to provide

### 1. One FLORIS YAML per park (used by step 1)

Copy [`park_example.yaml`](park_example.yaml) to `park_A.yaml`, `park_B.yaml`, and so on. Every field in it is commented. You only **have to** edit the `farm` section:

| Field | What to put | Notes |
|---|---|---|
| `farm.layout_x` | x of each turbine, in **metres**, towards the **east** | Any origin works, for example the first turbine at 0. |
| `farm.layout_y` | y of each turbine, in **metres**, towards the **north** | Same length and order as `layout_x`. If y does not point north, every wake direction comes out rotated. |
| `farm.turbine_type` | `[nrel_5MW]`, `[iea_10MW]`, `[iea_15MW]`, `[iea_22MW]`, or your own turbine | Give one name for all turbines, or one per turbine. The rotor diameter matters most. |
| `farm.turbine_library_path` | *(optional)* folder that holds your own turbine YAML files | The path is relative to the folder you run the script from, not to the YAML. |

Things you may adapt:

- `flow_field.wind_shear`: about 0.10 offshore, 0.14 to 0.25 onshore.
- `flow_field.air_density`

Things you can leave alone:

- `flow_field.wind_directions`, `wind_speeds` and `turbulence_intensities`. The script overwrites them.
- The `wake` section (Gauss-Curl Hybrid, the FLORIS default).

**Converting GPS coordinates to metres:**

```python
from pyproj import Transformer
t = Transformer.from_crs("EPSG:4326", "EPSG:32631", always_xy=True)  # UTM 31N, change the zone for your site
x, y = t.transform(lons, lats)
x, y = x - x.min(), y - y.min()
```

**Using your real turbine:**

1. Copy a file from `<site-packages>/floris/turbine_library/` into `turbines/my_turbine.yaml`.
2. In that file, set `turbine_type: my_turbine`, `hub_height` and `rotor_diameter`.
3. Fill `power_thrust_table` (`wind_speed`, `power` in kW, `thrust_coefficient`) from the manufacturer's datasheet.
4. In the park YAML, set `turbine_library_path: turbines` and `turbine_type: [my_turbine]`.

**Checking that a YAML loads:**

```bash
python -c "from floris import FlorisModel; print(FlorisModel('park_A.yaml').n_turbines)"
```

### 2. One predictions CSV per park (used by step 2)

You need one row per time step. The default column names are below; change them in `COLS` if yours differ.

| Column | Content |
|---|---|
| `time` | timestamp |
| `wind_direction` | degrees, direction the wind comes **from** (270 = west) |
| `wind_speed` | m/s (observed if available), used for the wind-speed bins |
| `prediction` | predicted power |
| `observation` | observed power |

## Configuration to edit in the scripts

**`1_wake_directions.py`**

- `PARKS = {"park_A": "park_A.yaml", ...}`
- `REF_WIND_SPEED`
- `TURBULENCE_INTENSITY`
- `WAKE_LOSS_THRESHOLD` (default 5% farm loss gives a "wake" direction)

**`2_analyse_predictions.py`**

- `PARKS = {"park_A": "park_A.csv", ...}`: use the **same park names** as in step 1.
- `COLS`, `BIN_WIDTH`, `MIN_COUNT`
- `PLOT_START` / `PLOT_END`

## Running

From the folder that contains the YAML and CSV files:

```bash
python 1_wake_directions.py      # -> out/wake_directions.csv + wake roses + layouts
python 2_analyse_predictions.py  # -> out/<park>_*.png / .csv + out/summary_all_parks.csv
```

All outputs go to `out/`. Each script's docstring lists the files it writes.

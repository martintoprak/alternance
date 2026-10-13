"""
STEP 2 - Label your predictions as wake / no wake, then compare them
at the same wind speed.

Reads:
  out/wake_directions.csv  (from 1_wake_directions.py)
  your predictions CSV for each park (time, wind direction, wind speed,
  predicted power, observed power)

For each time step, the wind direction is rounded to the nearest degree and
looked up in wake_directions.csv for that park. Your data is not modified,
only a wake_loss and a wake_class column are added.

Then time steps are grouped into wind-speed bins. Inside each bin, wake and
no_wake time steps have the same wind speed, so differences between the two
groups come from the wake.

Output per park:
  out/<park>_with_wake.csv    your data + wake_loss + wake_class
  out/<park>_directions.png   left: FLORIS wake loss vs direction,
                              right: how often the wind blew from each direction
                              over your period (red = wake directions)
  out/<park>_pred_vs_obs.png  predicted vs observed power, wake vs no wake,
                              with bias, MAE, RMSE and correlation
  out/<park>_timeseries.png   predictions colored by wake / no wake
  out/<park>_by_speed.csv     n, mean obs, mean pred, bias, MAE, RMSE per bin and class
  out/<park>_by_speed.png     4 panels: obs & pred, bias, MAE, counts
And:
  out/summary_all_parks.csv   one line per park, with wake-minus-no_wake
                              differences at matched wind speed
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ============================ CONFIGURATION ============================
# One predictions file per park (same park names as in 1_wake_directions.py)
PARKS = {
    "park_A": "park_A.csv",
    # "park_B": "park_B.csv",
}

# Column names in your CSV files
COLS = {
    "time": "time",
    "wind_dir": "wind_direction",   # degrees, direction the wind comes FROM (270 = west)
    "wind_speed": "wind_speed",     # used for the bins (observed if you have it)
    "pred": "prediction",           # predicted power
    "obs": "observation",           # observed power
}

BIN_WIDTH = 1.0     # m/s
MIN_COUNT = 20      # bins with fewer points in a class are not shown
PLOT_START, PLOT_END = None, None   # e.g. "2026-01-01", "2026-01-31" to zoom the time series
DIR_BIN = 5         # degrees, sector width of the wind direction rose
OUT_DIR = Path("out")
COLORS = {"no_wake": "#2a7fd4", "wake": "#d64545"}
LABELS = {"no_wake": "No wake", "wake": "Wake"}
# =======================================================================


def label_wake(df, wake_table):
    wd = np.round(np.mod(df[COLS["wind_dir"]].to_numpy(), 360)).astype(int) % 360
    table = wake_table.set_index("wind_direction")
    df["wake_loss"] = table.loc[wd, "wake_loss"].to_numpy()
    df["wake_class"] = np.where(table.loc[wd, "wake"].to_numpy(), "wake", "no_wake")
    return df


def _compass(ax):
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)          # clockwise, N on top


def plot_directions(df, wake_table, park, out):
    """Left: FLORIS wake loss per direction. Right: wind direction frequency over the period."""
    wt = wake_table.sort_values("wind_direction")
    loss = wt["wake_loss"].to_numpy() * 100
    is_wake = wt["wake"].to_numpy()

    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(12, 6), subplot_kw={"projection": "polar"})

    theta = np.deg2rad(np.arange(361))
    ax_l.plot(theta, np.append(loss, loss[0]), color=COLORS["wake"])
    ax_l.fill(theta, np.append(loss, loss[0]), color=COLORS["wake"], alpha=0.25)
    _compass(ax_l)
    ax_l.set_title("FLORIS farm wake loss (%)\nvs wind direction (from)", pad=18)

    # Frequency of each sector over the period
    wd = np.mod(df[COLS["wind_dir"]].to_numpy(), 360)
    edges = np.arange(0, 360 + DIR_BIN, DIR_BIN)
    # Shift by half a sector so that e.g. 0 deg sits in the middle of the north sector
    counts, _ = np.histogram(np.mod(wd + DIR_BIN / 2, 360), bins=edges)
    freq = counts / counts.sum() * 100
    sector_dirs = np.mod(edges[:-1], 360).astype(int)       # sector centered on this direction
    sector_wake = is_wake[sector_dirs]
    ax_r.bar(np.deg2rad(sector_dirs), freq, width=np.deg2rad(DIR_BIN) * 0.95,
             color=np.where(sector_wake, COLORS["wake"], COLORS["no_wake"]), alpha=0.85)
    _compass(ax_r)
    share_wake = (df["wake_class"] == "wake").mean()
    ax_r.set_title(f"Wind direction over the period (% of time)\n"
                   f"red = wake directions: {share_wake:.0%} of the time", pad=18)

    fig.suptitle(park, fontsize=14)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def metrics(d):
    err = d[COLS["pred"]] - d[COLS["obs"]]
    return {"n": len(d), "bias": err.mean(), "mae": err.abs().mean(),
            "rmse": np.sqrt((err ** 2).mean()),
            "corr": d[COLS["pred"]].corr(d[COLS["obs"]])}


def plot_pred_vs_obs(df, park, out):
    d = df.dropna(subset=[COLS["pred"], COLS["obs"]])
    lim = [min(d[COLS["pred"]].min(), d[COLS["obs"]].min()),
           max(d[COLS["pred"]].max(), d[COLS["obs"]].max())]

    fig, axes = plt.subplots(1, 2, figsize=(12, 6), sharex=True, sharey=True)
    for ax, cls in zip(axes, ["no_wake", "wake"]):
        s = d[d["wake_class"] == cls]
        ax.scatter(s[COLS["obs"]], s[COLS["pred"]], s=4, alpha=0.3, color=COLORS[cls])
        ax.plot(lim, lim, "k--", lw=1)
        m = metrics(s)
        ax.text(0.03, 0.97,
                f"n = {m['n']}\nbias = {m['bias']:.3f}\nMAE = {m['mae']:.3f}\n"
                f"RMSE = {m['rmse']:.3f}\ncorr = {m['corr']:.3f}",
                transform=ax.transAxes, va="top", fontsize=10,
                bbox=dict(facecolor="white", alpha=0.8, edgecolor="0.8"))
        ax.set_title(f"{LABELS[cls]} directions")
        ax.set_xlabel("Observed power")
        ax.grid(alpha=0.3)
        ax.set_aspect("equal")
    axes[0].set_ylabel("Predicted power")
    fig.suptitle(f"{park}: predictions vs observations", fontsize=14)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def plot_timeseries(df, park, out):
    t_all = df[COLS["time"]]
    keep = pd.Series(True, index=df.index)
    if PLOT_START:
        keep &= t_all >= pd.Timestamp(PLOT_START)
    if PLOT_END:
        keep &= t_all <= pd.Timestamp(PLOT_END)
    d = df[keep].reset_index(drop=True)

    t, y = d[COLS["time"]], d[COLS["pred"]]
    w = (d["wake_class"] == "wake").to_numpy()

    fig, ax = plt.subplots(figsize=(14, 4.5))
    ax.plot(t, y, color="0.8", lw=0.5, zorder=1)
    ax.scatter(t[~w], y[~w], s=4, color=COLORS["no_wake"], label="No wake", zorder=2)
    ax.scatter(t[w], y[w], s=4, color=COLORS["wake"], label="Wake", zorder=3)
    ax.set_title(f"{park}: predictions colored by wake ({w.mean():.0%} of time steps in wake)")
    ax.set_ylabel(COLS["pred"])
    ax.legend(loc="upper right", markerscale=3)
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def stats_by_speed(df):
    df = df.dropna(subset=[COLS["wind_speed"], COLS["pred"], COLS["obs"]]).copy()
    df["error"] = df[COLS["pred"]] - df[COLS["obs"]]
    df["abs_error"] = df["error"].abs()
    df["sq_error"] = df["error"] ** 2

    ws = df[COLS["wind_speed"]]
    edges = np.arange(np.floor(ws.min() / BIN_WIDTH) * BIN_WIDTH, ws.max() + BIN_WIDTH, BIN_WIDTH)
    df["ws_bin"] = pd.cut(ws, edges, right=False)

    st = (df.groupby(["ws_bin", "wake_class"], observed=True)
            .agg(n=("error", "size"),
                 obs_mean=(COLS["obs"], "mean"),
                 pred_mean=(COLS["pred"], "mean"),
                 bias=("error", "mean"),
                 mae=("abs_error", "mean"),
                 rmse=("sq_error", lambda s: np.sqrt(s.mean())))
            .reset_index())
    st["ws"] = st["ws_bin"].apply(lambda b: b.mid).astype(float)
    st = st[st["n"] >= MIN_COUNT].drop(columns="ws_bin")
    return df, st


def speed_matched_summary(park, df, st):
    """Overall metrics + wake-minus-no_wake differences at matched wind speed."""
    row = {"park": park}
    for cls in ["no_wake", "wake"]:
        for k, v in metrics(df[df["wake_class"] == cls]).items():
            row[f"{k}_{cls}"] = v

    wide = st.pivot(index="ws", columns="wake_class",
                    values=["n", "bias", "mae", "obs_mean", "pred_mean"])
    if ("n", "wake") in wide and ("n", "no_wake") in wide:
        wide = wide.dropna()
        w = wide[("n", "wake")]
        for m in ["bias", "mae", "obs_mean", "pred_mean"]:
            diff = wide[(m, "wake")] - wide[(m, "no_wake")]
            row[f"{m}_diff_same_speed"] = np.average(diff, weights=w) if w.sum() else np.nan
    return row


def plot_by_speed(park, st, out):
    fig, axes = plt.subplots(4, 1, figsize=(10, 12), sharex=True,
                             gridspec_kw={"height_ratios": [3, 2, 2, 1.2]})
    ax_val, ax_bias, ax_mae, ax_n = axes
    off = BIN_WIDTH * 0.12

    for cls, dx in [("no_wake", -off), ("wake", off)]:
        s = st[st["wake_class"] == cls]
        c = COLORS[cls]
        ax_val.plot(s["ws"], s["obs_mean"], "-", color=c, lw=2, label=f"{LABELS[cls]}: observed")
        ax_val.plot(s["ws"], s["pred_mean"], "--", color=c, lw=2, label=f"{LABELS[cls]}: predicted")
        ax_bias.plot(s["ws"], s["bias"], "o-", color=c, label=LABELS[cls])
        ax_mae.plot(s["ws"], s["mae"], "o-", color=c, label=LABELS[cls])
        ax_n.bar(s["ws"] + dx, s["n"], width=BIN_WIDTH * 0.22, color=c)

    ax_val.set_ylabel("Mean power")
    ax_val.set_title(f"{park}: wake vs no wake at the same wind speed")
    ax_val.legend(fontsize=8, ncol=2)
    ax_bias.axhline(0, color="k", lw=0.8)
    ax_bias.set_ylabel("Bias (pred - obs)")
    ax_bias.legend(fontsize=8)
    ax_mae.set_ylabel("MAE")
    ax_mae.legend(fontsize=8)
    ax_n.set_ylabel("Points")
    ax_n.set_xlabel("Wind speed (m/s)")
    for ax in axes:
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def main():
    wake_all = pd.read_csv(OUT_DIR / "wake_directions.csv")
    summary = []
    for park, csv_path in PARKS.items():
        wake_table = wake_all[wake_all["park"] == park]
        if wake_table.empty:
            print(f"{park}: not found in wake_directions.csv, run 1_wake_directions.py first")
            continue

        df = pd.read_csv(csv_path, parse_dates=[COLS["time"]])
        df = df.dropna(subset=[COLS["wind_dir"]]).reset_index(drop=True)
        df = label_wake(df, wake_table)
        df.to_csv(OUT_DIR / f"{park}_with_wake.csv", index=False)
        plot_directions(df, wake_table, park, OUT_DIR / f"{park}_directions.png")
        plot_pred_vs_obs(df, park, OUT_DIR / f"{park}_pred_vs_obs.png")
        plot_timeseries(df, park, OUT_DIR / f"{park}_timeseries.png")

        df_err, st = stats_by_speed(df)
        st.to_csv(OUT_DIR / f"{park}_by_speed.csv", index=False)
        plot_by_speed(park, st, OUT_DIR / f"{park}_by_speed.png")
        summary.append(speed_matched_summary(park, df_err, st))
        print(f"{park}: {(df['wake_class'] == 'wake').mean():.1%} of time steps in wake")

    summary = pd.DataFrame(summary)
    summary.to_csv(OUT_DIR / "summary_all_parks.csv", index=False)
    pd.set_option("display.width", 200)
    print()
    print(summary.round(3).to_string(index=False))


if __name__ == "__main__":
    main()

from glob import glob
from invoke import task
from os import makedirs
from os.path import join

import matplotlib.pyplot as plt
import pandas as pd

from tasks.util.env import MPL_STYLE_FILE, PLOTS_FORMAT, PLOTS_ROOT, PROJ_ROOT

RESULTS_DIR = join(PROJ_ROOT, "results", "migration")
PLOTS_DIR = join(PLOTS_ROOT, "migration")
OUT_FILE = join(PLOTS_DIR, "runtime.{}".format(PLOTS_FORMAT))
PATTERNS = ["//", "\\\\", "||", "-"]


def _read_results():
    result_dict = {}

    for csv in glob(join(RESULTS_DIR, "migration_*.csv")):
        results = pd.read_csv(csv)

        check = int(csv.split("_")[-1].split(".")[0])
        nproc = int(csv.split("_")[1])

        if nproc not in result_dict:
            result_dict[nproc] = {}

        result_dict[nproc][check] = [
            results["Time"].mean(),
            results["Time"].sem(),
        ]

    return result_dict


@task(default=True)
def plot(ctx):
    """
    Plot migration figure
    """
    # Use our matplotlib style file
    plt.style.use(MPL_STYLE_FILE)

    makedirs(PLOTS_DIR, exist_ok=True)

    # Load results
    migration_results = _read_results()

    # Plot results
    fig, ax = plt.subplots(figsize=(6, 2))
    num_cols = 2  # len(migration_results.keys())
    col_width = float(1 / num_cols)
    for ind, nproc in enumerate([4, 8]):
        x = [int(key) for key in migration_results[nproc].keys()]
        x.sort()
        if ind < (num_cols / 2):
            factor = -1
        else:
            factor = 1
        disp_x = [xs + factor * col_width / 2 for xs in x]

        y = [migration_results[nproc][xs][0] for xs in x]
        print(x)
        print(y)
        yerr = [migration_results[nproc][xs][1] for xs in x]
        ax.bar(
            disp_x,
            y,
            yerr=yerr,
            width=col_width,
            hatch=PATTERNS[ind],
            edgecolor="black",
        )

    # Prepare legend
    ax.legend(["{} processes".format(np) for np in [4, 8]])

    # Aesthetics
    ax.set_ylabel("Elapsed time [s]")
    ax.set_xlabel("Percentage of execution at which migration takes place [%]")
    ax.set_xticklabels(
        [
            0,
            "single host",
            "20",
            "40",
            "60",
            "80",
            "no migration",
        ]
    )

    fig.tight_layout()
    # plt.gca().set_aspect(0.4)
    plt.savefig(OUT_FILE, format=PLOTS_FORMAT, bbox_inches="tight")

    return

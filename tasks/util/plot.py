from matplotlib.patches import Polygon
from os import makedirs
from os.path import join
from subprocess import run
from tasks.util.env import PLOTS_ROOT
from tasks.util.faasm import get_faasm_version

_PLOT_COLORS = {
    "granny": (1, 0.4, 0.4),
    "granny-no-migrate": (0.29, 0.63, 0.45),
    "granny-no-elastic": (0.29, 0.63, 0.45),
    "batch": (0.2, 0.6, 1.0),
    "slurm": (0.3, 0.3, 0.3),
}

UBENCH_PLOT_COLORS = [
    (1, 0.4, 0.4),
    (0.29, 0.63, 0.45),
    (0.2, 0.6, 1.0),
    (0.3, 0.3, 0.3),
    (0.6, 0.4, 1.0),
    (1.0, 0.8, 0.4),
]

PLOT_PATTERNS = ["//", "\\\\", "||", "-", "*-", "o-"]
SINGLE_COL_FIGSIZE = (6, 3)


def fix_hist_step_vertical_line_at_end(ax):
    axpolygons = [
        poly for poly in ax.get_children() if isinstance(poly, Polygon)
    ]
    for poly in axpolygons:
        poly.set_xy(poly.get_xy()[:-1])


def _do_get_for_baseline(workload, baseline, color=False, label=False):
    if workload == "omp-elastic":
        if baseline == "granny":
            this_label = "granny-no-elastic"
            if label:
                return this_label
            if color:
                return _PLOT_COLORS[this_label]
        if baseline == "granny-elastic":
            this_label = "granny"
            if label:
                return this_label
            if color:
                return _PLOT_COLORS[this_label]
        if baseline == "batch" or baseline == "slurm":
            this_label = baseline
            if label:
                return this_label
            if color:
                return _PLOT_COLORS[this_label]

        raise RuntimeError(
            "Unrecognised baseline ({}) for workload: {}".format(
                baseline, workload
            )
        )

    if workload == "mpi-migrate":
        if baseline == "granny":
            this_label = "granny-no-migrate"
            if label:
                return this_label
            if color:
                return _PLOT_COLORS[this_label]
        if baseline == "granny-migrate":
            this_label = "granny"
            if label:
                return this_label
            if color:
                return _PLOT_COLORS[this_label]
        if baseline == "batch" or baseline == "slurm":
            this_label = baseline
            if label:
                return this_label
            if color:
                return _PLOT_COLORS[this_label]

        raise RuntimeError(
            "Unrecognised baseline ({}) for workload: {}".format(
                baseline, workload
            )
        )

    if workload == "mpi-spot":
        if baseline == "granny":
            this_label = "granny"
            if label:
                return this_label
            if color:
                return _PLOT_COLORS[this_label]
        if baseline == "batch" or baseline == "slurm":
            this_label = baseline
            if label:
                return this_label
            if color:
                return _PLOT_COLORS[this_label]

        raise RuntimeError(
            "Unrecognised baseline ({}) for workload: {}".format(
                baseline, workload
            )
        )


def get_color_for_baseline(workload, baseline):
    return _do_get_for_baseline(workload, baseline, color=True)


def get_label_for_baseline(workload, baseline):
    return _do_get_for_baseline(workload, baseline, label=True)


def save_plot(fig, plot_dir, plot_name):
    fig.tight_layout()
    versioned_dir = join(PLOTS_ROOT, get_faasm_version())
    makedirs(versioned_dir, exist_ok=True)
    for plot_format in ["png", "pdf"]:
        this_plot_name = "{}.{}".format(plot_name, plot_format)
        plot_file = join(plot_dir, this_plot_name)
        fig.savefig(plot_file, format=plot_format, bbox_inches="tight")
        print("Plot saved to: {}".format(plot_file))

        # Also make a copy in the tag directory
        versioned_file = join(versioned_dir, this_plot_name)
        run(
            "cp {} {}".format(plot_file, versioned_file),
            shell=True,
            check=True,
        )

    hostname = (
        run("hostname", shell=True, check=True, capture_output=True)
        .stdout.decode("utf-8")
        .strip()
    )
    tmp_file = "/tmp/{}".format(this_plot_name)
    print(
        "scp {}:{} {} && evince {} &".format(
            hostname, plot_file, tmp_file, tmp_file
        )
    )

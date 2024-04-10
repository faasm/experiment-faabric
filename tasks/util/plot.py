from os import makedirs
from os.path import join
from subprocess import run
from tasks.util.env import PLOTS_ROOT
from tasks.util.faasm import get_faasm_version

PLOT_COLORS = {
    "granny": (1, 0.4, 0.4),
    "granny-migrate": (0.29, 0.63, 0.45),
    "batch": (0.2, 0.6, 1.0),
    "slurm": (0.3, 0.3, 0.3),
}

PLOT_LABELS = {
    "granny": "granny",
    "native-1": "1-ctr-per-vm",
    "native-2": "2-ctr-per-vm",
    "native-4": "4-ctr-per-vm",
    "native-8": "8-ctr-per-vm",
}

PLOT_PATTERNS = ["//", "\\\\", "||", "-", "*-", "o-"]
SINGLE_COL_FIGSIZE = (6, 3)


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

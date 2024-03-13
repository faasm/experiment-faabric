from glob import glob
from invoke import task
from os.path import join
from pandas import read_csv
from tasks.util.lulesh import (
    LULESH_RESULTS_DIR,
)


def _read_results():
    glob_str = "lulesh_*.csv"
    result_dict = {}

    for csv in glob(join(LULESH_RESULTS_DIR, glob_str)):
        baseline = csv.split("_")[1].split(".")[0]

        if baseline not in result_dict:
            result_dict[baseline] = {}

        results = read_csv(csv)
        grouped = results.groupby("NumThreads", as_index=False)

        for nt in grouped.mean()["NumThreads"].to_list():
            index = grouped.mean()["NumThreads"].to_list().index(nt)
            result_dict[baseline][nt] = {
                "mean": grouped.mean()["Time"].to_list()[index],
                "sem": grouped.sem()["Time"].to_list()[index],
            }

    return result_dict


@task(default=True)
def plot(ctx, plot_elapsed_times=True):
    """
    Plot the LAMMPS results
    """
    pass
    # TODO: LULESH results are so bad that we don't bother implementing the
    # plot just yet
    # makedirs(LULESH_PLOTS_DIR, exist_ok=True)
    # result_dict = _read_results()

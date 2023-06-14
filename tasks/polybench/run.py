from invoke import task
from os import makedirs
from os.path import basename, join
from tasks.polybench.util import (
    POLYBENCH_FUNCS,
    POLYBENCH_USER,
)
from tasks.util.env import (
    MPI_MIGRATE_FAASM_USER,
    MPI_MIGRATE_FAASM_FUNC,
    LAMMPS_MIGRATION_FAASM_USER,
    LAMMPS_MIGRATION_FAASM_FUNC,
    RESULTS_DIR,
)
from tasks.util.faasm import (
    get_faasm_exec_time_from_json,
    get_faasm_invoke_host_port,
    # TODO(planner)
    # get_faasm_planner_host_port,
    get_faasm_worker_ips,
    flush_workers,
    post_async_msg_and_get_result_json,
    reset_planner,
    wait_for_workers as wait_for_planner_workers,
)
from time import sleep


def _get_csv_name(baseline, bench):
    return "polybench_{}_{}.csv".format(baseline, bench)


def _init_csv_file(csv_name):
    result_dir = join(RESULTS_DIR, "polybench")
    makedirs(result_dir, exist_ok=True)

    result_file = join(result_dir, csv_name)
    makedirs(RESULTS_DIR, exist_ok=True)
    with open(result_file, "w") as out_file:
        out_file.write("Run,Time\n")

    return result_file


def _write_csv_line(csv_name, run_num, actual_time):
    result_dir = join(RESULTS_DIR, "polybench")
    result_file = join(result_dir, csv_name)
    with open(result_file, "a") as out_file:
        out_file.write(
            "{},{:.2f}\n".format(run_num, actual_time)
        )


@task(default=True)
def granny(ctx, bench=None, repeats=3):
    """
    Run the PolyBench/C microbenchmark
    """
    # TODO(planner): uncomment when planner is upstreamed
    # reset_planner()
    # wait_for_planner_workers(num_workers)
    num_warmup_runs = 1

    if bench:
        if bench not in POLYBENCH_FUNCS:
            raise RuntimeError(
                "Unrecognised benchmark: {}. Must be one in: {}".format(
                    bench, POLYBENCH_FUNCS
                )
            )
        poly_benchmarks = [bench]
    else:
        poly_benchmarks = POLYBENCH_FUNCS

    # Url and headers for requests
    # TODO(planner):
    # host, port = get_faasm_planner_host_port()
    host, port = get_faasm_invoke_host_port()
    url = "http://{}:{}".format(host, port)

    for poly_bench in poly_benchmarks:
        csv_name = _get_csv_name("granny", poly_bench)
        _init_csv_file(csv_name)

        # First, flush the host state
        flush_workers()

        # Do the repeats + 1 warm-up round
        for run_num in range(repeats + num_warmup_runs):
            msg = {
                "user": POLYBENCH_USER,
                "function": poly_bench,
                "async": True,
            }
            result_json = post_async_msg_and_get_result_json(msg, url)
            actual_time = get_faasm_exec_time_from_json(result_json)
            if run_num > num_warmup_runs:
                _write_csv_line(
                    csv_name, (run_num - num_warmup_runs), actual_time
                )

            print("Actual time: {}".format(actual_time))
            sleep(2)


@task
def native(ctx, bench=None, repeats=3):
    pass

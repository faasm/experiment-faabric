from faasmctl.util.flush import flush_workers
from faasmctl.util.planner import reset as reset_planner
from invoke import task
from os import makedirs
from os.path import join
from tasks.polybench.util import (
    POLYBENCH_FUNCS,
    POLYBENCH_NATIVE_DOCKER_BUILD_DIR,
    POLYBENCH_USER,
)
from tasks.util.env import RESULTS_DIR
from tasks.util.faasm import (
    get_faasm_exec_time_from_json,
    # TODO(planner)
    # get_faasm_planner_host_port,
    post_async_msg_and_get_result_json,
    # TODO(planner)
    # wait_for_workers as wait_for_planner_workers,
)
from tasks.util.openmpi import get_native_mpi_pods, run_kubectl_cmd
from time import sleep

NUM_WARMUP_RUNS = 1


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
        out_file.write("{},{:.5f}\n".format(run_num, actual_time))


def _get_poly_benchmarks(bench):
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

    return poly_benchmarks


@task(default=True)
def granny(ctx, bench=None, repeats=3):
    """
    Run the PolyBench/C microbenchmark with Granny (i.e. WASM)
    """
    reset_planner()
    # TODO(planner): uncomment when planner is upstreamed
    # wait_for_planner_workers(num_workers)

    poly_benchmarks = _get_poly_benchmarks(bench)

    for poly_bench in poly_benchmarks:
        csv_name = _get_csv_name("granny", poly_bench)
        _init_csv_file(csv_name)

        # First, flush the host state
        flush_workers()

        # Do the repeats + 1 warm-up round
        for run_num in range(repeats + NUM_WARMUP_RUNS):
            msg = {
                "user": POLYBENCH_USER,
                "function": poly_bench,
                "async": True,
            }
            result_json = post_async_msg_and_get_result_json(msg)
            actual_time = get_faasm_exec_time_from_json(result_json)
            if run_num >= NUM_WARMUP_RUNS:
                _write_csv_line(
                    csv_name, (run_num - NUM_WARMUP_RUNS), actual_time
                )

            print("Actual time: {}".format(actual_time))
            sleep(2)


@task
def native(ctx, bench=None, repeats=3):
    """
    Run the PolyBench/C microbenchmark in nativ eexecution
    """
    pod_names, _ = get_native_mpi_pods("polybench")
    master_pod = pod_names[0]

    poly_benchmarks = _get_poly_benchmarks(bench)

    for poly_bench in poly_benchmarks:
        csv_name = _get_csv_name("native", poly_bench)
        _init_csv_file(csv_name)

        # Do the repeats + 1 warm-up round
        for run_num in range(repeats + NUM_WARMUP_RUNS):
            poly_cmd = join(POLYBENCH_NATIVE_DOCKER_BUILD_DIR, poly_bench)
            exec_cmd = [
                "exec",
                master_pod,
                "--",
                "bash -c 'TIMEFORMAT=%R; time {}'".format(poly_cmd),
            ]
            # Note that the `time` command prints to `stderr`
            exec_output = run_kubectl_cmd(
                "polybench", " ".join(exec_cmd), capture_stderr=True
            )
            actual_time = float(exec_output)

            if run_num >= NUM_WARMUP_RUNS:
                _write_csv_line(
                    csv_name, (run_num - NUM_WARMUP_RUNS), actual_time
                )

            print("Actual time: {}".format(actual_time))
            sleep(2)

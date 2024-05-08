from faasmctl.util.planner import get_available_hosts
from faasmctl.util.planner import reset as reset_planner, set_planner_policy
from invoke import task
from os import makedirs
from os.path import join
from tasks.util.faasm import (
    get_faasm_exec_time_from_json,
    post_async_msg_and_get_result_json,
)
from tasks.util.elastic import (
    ELASTIC_KERNEL,
    ELASTIC_RESULTS_DIR,
    OPENMP_ELASTIC_FUNCTION,
    OPENMP_ELASTIC_USER,
    get_elastic_input_data,
)
from tasks.util.kernels import get_openmp_kernel_cmdline

EXPECTED_NUM_VMS = 1
TOTAL_NUM_THREADS = [1, 2, 3, 4, 5, 6, 7, 8]


def _init_csv_file(csv_name):
    makedirs(ELASTIC_RESULTS_DIR, exist_ok=True)

    result_file = join(ELASTIC_RESULTS_DIR, csv_name)
    with open(result_file, "w") as out_file:
        out_file.write("NumThreads,Run,ExecTimeSecs\n")


def _write_csv_line(csv_name, num_threads, run, exec_time):
    result_file = join(ELASTIC_RESULTS_DIR, csv_name)
    with open(result_file, "a") as out_file:
        out_file.write("{},{},{}\n".format(num_threads, run, exec_time))


def has_execution_failed(results_json):
    for result in results_json:
        if "returnValue" in result and result["returnValue"] != 0:
            return True

        if "output_data" in result:
            if "ERROR" in result["output_data"]:
                return True
            if "Call failed" in result["output_data"]:
                return True

    return False


@task(default=True)
def wasm(ctx, num_threads=None, elastic=False, repeats=1):
    """
    Run the OpenMP Kernels
    """
    set_planner_policy("bin-pack")

    avail_hosts = get_available_hosts().hosts
    num_vms = len(avail_hosts)
    """
    assert num_vms == EXPECTED_NUM_VMS, "Expected {} VMs got: {}!".format(
        EXPECTED_NUM_VMS, num_vms
    )
    """

    if num_threads is not None:
        num_threads = [num_threads]
    else:
        num_threads = TOTAL_NUM_THREADS

    reset_planner(num_vms)

    csv_name = "openmp_{}_granny.csv".format("elastic" if elastic else "no-elastic")
    _init_csv_file(csv_name)

    for nthread in num_threads:
        for r in range(int(repeats)):
            print(
                "Running OpenMP elastic experiment with {} threads (elastic: {} - repeat: {}/{})".format(
                    nthread, elastic, r + 1, repeats
                )
            )
            user = OPENMP_ELASTIC_USER
            func = OPENMP_ELASTIC_FUNCTION
            cmdline = get_openmp_kernel_cmdline(ELASTIC_KERNEL, nthread)
            msg = {
                "user": user,
                "function": func,
                "cmdline": cmdline,
                "input_data": get_elastic_input_data(),
                "isOmp": True,
                "ompNumThreads": nthread,
            }
            req = {
                "user": user,
                "function": func,
                "singleHostHint": True,
                "elasticScaleHint": elastic,
            }

            # Note that when executing with just two iterations, the first one
            # will always be pre-loaded by the planner (so not elastically
            # scaled) thus naturally fitting the goal of our plot
            result_json = post_async_msg_and_get_result_json(msg, req_dict=req)
            actual_time = get_faasm_exec_time_from_json(
                result_json, check=True
            )
            _write_csv_line(csv_name, nthread, r, actual_time)
            # TODO: delete me
            print("Actual time: {}".format(actual_time))

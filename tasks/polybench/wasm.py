from invoke import task
from os.path import join
from tasks.polybench.util import (
    POLYBENCH_DOCKER_DIR,
    POLYBENCH_FUNCS,
    POLYBENCH_USER,
)
from tasks.util.upload import upload_wasm


@task()
def upload(ctx):
    """
    Upload the migration microbenchmark function to Granny
    """
    wasm_file_details = []
    for func in POLYBENCH_FUNCS:
        func_file = join(POLYBENCH_DOCKER_DIR, func, "function.wasm")
        wasm_file_details += [
            {
                "wasm_file": func_file,
                "wasm_user": POLYBENCH_USER,
                "wasm_function": func,
                "copies": 1,
            }
        ]

    upload_wasm(wasm_file_details)

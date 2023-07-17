from faasmctl.util.upload import upload_file as faasmctl_upload_file
from invoke import task
from os.path import exists, join
from tasks.lammps.env import (
    LAMMPS_DIR,
    LAMMPS_FAASM_DATA_PREFIX,
    get_faasm_benchmark,
)


@task(default=True, iterable=["bench"])
def upload(ctx, bench):
    """
    Upload LAMMPS benchmark data to Faasm
    """
    for b in bench:
        _bench = get_faasm_benchmark(b)

        # Upload all data corresponding to the benchmark
        for data in _bench["data"]:
            file_name = data.split("/")[-1]
            host_path = join(LAMMPS_DIR, data + ".faasm")
            faasm_path = join(LAMMPS_FAASM_DATA_PREFIX, file_name)

            if not exists(host_path):
                print("Did not find data at {}".format(host_path))
                raise RuntimeError("Did not find LAMMPS data!")

            response = faasmctl_upload_file(host_path, faasm_path)

            if response.status_code != 200:
                raise RuntimeError("Error uploading LAMMPS data!")

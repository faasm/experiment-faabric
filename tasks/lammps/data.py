from invoke import task
from os.path import exists
import requests

from tasks.lammps.env import LAMMPS_DATA_FILE
from tasks.util.faasm import get_faasm_upload_host_port

FAASM_LOCAL_SHARED_DIR = "/usr/local/faasm/shared"

RELATIVE_PATH = "lammps-data/in.controller"


@task(default=True)
def upload(ctx, host_path = LAMMPS_DATA_FILE, faasm_path = RELATIVE_PATH):
    """
    Upload LAMMPS data to Faasm
    """
    if not exists(LAMMPS_DATA_FILE):
        print("Did not find data at {}".format(LAMMPS_DATA_FILE))
        exit(1)

    host, port = get_faasm_upload_host_port()
    url = "http://{}:{}/file".format(host, port)
    print("Uploading LAMMPS data to {}".format(url))
    response = requests.put(
        url,
        data=open(LAMMPS_DATA_FILE, "rb"),
        headers={"FilePath": RELATIVE_PATH},
    )

    print("Response {}: {}".format(response.status_code, response.text))

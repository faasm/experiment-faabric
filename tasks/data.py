from invoke import task
from os import makedirs
from os.path import join, exists
from shutil import copy
import requests

from tasks.util import LAMMPS_DIR

FAASM_LOCAL_SHARED_DIR = "/usr/local/faasm/shared"

LOCAL_DEST_DIR = join(FAASM_LOCAL_SHARED_DIR, "lammps-data")
LOCAL_DEST_FILE = join(LOCAL_DEST_DIR, "in.controller")

RELATIVE_PATH = "lammps-data/in.controller"

DATA_FILE = join(LAMMPS_DIR, "examples", "controller", "in.controller.wall")


@task(default=True)
def upload(ctx, local=False, host="localhost", port=8002):
    """
    Upload LAMMPS data to Faasm
    """

    if not exists(DATA_FILE):
        print("Did not find data at {}".format(DATA_FILE))
        exit(1)

    if local:
        makedirs(LOCAL_DEST_DIR)

        print("Copying {} -> {}".format(DATA_FILE, LOCAL_DEST_FILE))
        copy(DATA_FILE, LOCAL_DEST_FILE)
    else:
        url = "http://{}:{}/file".format(host, port)
        print("Uploading LAMMPS data to {}".format(url))
        response = requests.put(
            url,
            data=open(DATA_FILE, "rb"),
            headers={"FilePath": RELATIVE_PATH},
        )

        print("Response {}: {}".format(response.status_code, response.text))

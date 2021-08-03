from os.path import dirname, realpath, expanduser, join, exists
from shutil import rmtree
from os import makedirs


HOME_DIR = expanduser("~")
PROJ_ROOT = dirname(dirname(realpath(__file__)))
NATIVE_BUILD_DIR = join(PROJ_ROOT, "build", "native")
NATIVE_INSTALL_DIR = join(PROJ_ROOT, "build", "native-install")
WASM_BUILD_DIR = join(PROJ_ROOT, "build", "wasm")
WASM_INSTALL_DIR = join(PROJ_ROOT, "build", "wasm-install")
LAMMPS_DIR = "{}/third-party/lammps".format(PROJ_ROOT)

FAASM_USER = "lammps"
FAASM_FUNC = "main"


def get_version():
    ver_file = join(PROJ_ROOT, "VERSION")

    with open(ver_file, "r") as fh:
        version = fh.read()
        version = version.strip()

    return version


def clean_dir(dir_path, clean):
    if clean and exists(dir_path):
        rmtree(dir_path)

    if not exists(dir_path):
        makedirs(dir_path)

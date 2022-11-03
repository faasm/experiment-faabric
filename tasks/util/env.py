from os.path import dirname, realpath, expanduser, join, exists
from shutil import rmtree
from os import makedirs
from subprocess import run

HOME_DIR = expanduser("~")
PROJ_ROOT = dirname(dirname(dirname(realpath(__file__))))
FAASM_ROOT = join(HOME_DIR, "faasm")

NATIVE_BUILD_DIR = join(PROJ_ROOT, "build", "native")
NATIVE_INSTALL_DIR = join(PROJ_ROOT, "build", "native-install")

WASM_BUILD_DIR = join(PROJ_ROOT, "build", "wasm")
WASM_INSTALL_DIR = join(PROJ_ROOT, "build", "wasm-install")

RESULTS_DIR = join(PROJ_ROOT, "results")

PLOTS_ROOT = join(PROJ_ROOT, "plots")
PLOTS_FORMAT = "pdf"
MPL_STYLE_FILE = join(PROJ_ROOT, "faasm.mplstyle")


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


def get_docker_tag(img_name):
    img_tag = "faasm/{}:{}".format(img_name, get_version())
    return img_tag


def push_docker_image(img_tag):
    run("docker push {}".format(img_tag), check=True, shell=True)

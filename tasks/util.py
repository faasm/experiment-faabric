from os.path import dirname, realpath, expanduser, join, exists
from shutil import rmtree
from os import makedirs
from subprocess import run, PIPE


HOME_DIR = expanduser("~")
PROJ_ROOT = dirname(dirname(realpath(__file__)))

KERNELS_NATIVE_DIR = join(PROJ_ROOT, "third-party", "kernels-native")
KERNELS_WASM_DIR = join(PROJ_ROOT, "third-party", "kernels")

LAMMPS_DIR = join(PROJ_ROOT, "third-party", "lammps")
LAMMPS_DATA_FILE = join(
    LAMMPS_DIR, "examples", "controller", "in.controller.wall"
)

NATIVE_BUILD_DIR = join(PROJ_ROOT, "build", "native")
NATIVE_INSTALL_DIR = join(PROJ_ROOT, "build", "native-install")
NATIVE_HOSTFILE = "/home/mpirun/hostfile"

DOCKER_PROJ_ROOT = "/code/experiment-lammps"
DOCKER_LAMMPS_DIR = join(DOCKER_PROJ_ROOT, "third-party", "lammps")
DOCKER_NATIVE_INSTALL_DIR = join(DOCKER_PROJ_ROOT, "build", "native-install")
DOCKER_LAMMPS_BINARY = join(DOCKER_NATIVE_INSTALL_DIR, "bin", "lmp")
DOCKER_LAMMPS_DATA_FILE = join(
    DOCKER_LAMMPS_DIR, "examples", "controller", "in.controller.wall"
)

WASM_BUILD_DIR = join(PROJ_ROOT, "build", "wasm")
WASM_INSTALL_DIR = join(PROJ_ROOT, "build", "wasm-install")

EXPERIMENTS_BASE_DIR = dirname(dirname(PROJ_ROOT))

FAASM_USER = "lammps"
FAASM_FUNC = "main"

IS_DOCKER = HOME_DIR.startswith("/root")

if IS_DOCKER:
    RESULTS_DIR = join(PROJ_ROOT, "results")
else:
    RESULTS_DIR = join(EXPERIMENTS_BASE_DIR, "results", "lammps")


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


def run_kubectl_cmd(cmd):
    kubecmd = "kubectl -n faasm-mpi-native {}".format(cmd)
    print(kubecmd)
    res = run(
        kubecmd,
        stdout=PIPE,
        stderr=PIPE,
        cwd=PROJ_ROOT,
        shell=True,
        check=True,
    )

    return res.stdout.decode("utf-8")


def get_pod_names_ips():
    # List all pods
    cmd_out = run_kubectl_cmd("get pods -o wide")
    print(cmd_out)

    # Split output into list of strings
    lines = cmd_out.split("\n")[1:]
    lines = [l.strip() for l in lines if l.strip()]

    pod_names = list()
    pod_ips = list()
    for line in lines:
        line_parts = line.split(" ")
        line_parts = [p.strip() for p in line_parts if p.strip()]

        pod_names.append(line_parts[0])
        pod_ips.append(line_parts[5])

    print("Got pods: {}".format(pod_names))
    print("Got IPs: {}".format(pod_ips))

    return pod_names, pod_ips


def get_docker_tag(img_name):
    img_tag = "faasm/{}:{}".format(img_name, get_version())
    return img_tag


def push_docker_image(img_tag):
    run("docker push {}".format(img_tag), check=True, shell=True)

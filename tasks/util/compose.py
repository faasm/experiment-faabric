from os.path import join
from subprocess import run
from tasks.util.env import ACR_NAME, FAABRIC_EXP_IMAGE_NAME, PROJ_ROOT, get_version

NUM_CORES_PER_CTR = 8
OPENMPI_COMPOSE_DIR = join(PROJ_ROOT, "tasks", "openmpi")
OPENMMPI_COMPOSE_FILE = join(OPENMPI_COMPOSE_DIR, "docker-compose.yml")
ENV_VARS = {
    "FAABRIC_EXP_IMAGE_NAME": "{}/{}:{}".format(ACR_NAME, FAABRIC_EXP_IMAGE_NAME, get_version()),
    "NUM_CORES_PER_VM": "{}".format(NUM_CORES_PER_CTR),
}


def run_compose_cmd(compose_cmd, capture_output=False):
    # Note that we actually run a docker command as we specify the container
    # by name
    docker_cmd = "docker compose -f {} {}".format(OPENMMPI_COMPOSE_FILE, compose_cmd)

    if capture_output:
        stdout = run(
            docker_cmd,
            shell=True,
            check=True,
            cwd=OPENMPI_COMPOSE_DIR,
            capture_output=True,
            env=ENV_VARS,
        ).stdout.decode("utf-8").strip()

        return stdout

    run(
        docker_cmd,
        shell=True,
        check=True,
        cwd=OPENMPI_COMPOSE_DIR,
        env=ENV_VARS,
    )


def get_compose_ctrs():
    ctr_ids = run_compose_cmd("ps -aq", capture_output=True).split("\n")

    docker_ip_cmd = "docker inspect -f '{{{{range.NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}}' {}"
    docker_name_cmd = "docker inspect -f '{{{{.Name}}}}' {}"

    ctr_ips = []
    ctr_names = []
    for ctr_id in ctr_ids:
        ctr_ips.append(run(
            docker_ip_cmd.format(ctr_id),
            shell=True,
            check=True,
            capture_output=True
        ).stdout.decode("utf-8").strip())

        ctr_names.append(run(
            docker_name_cmd.format(ctr_id),
            shell=True,
            check=True,
            capture_output=True
        ).stdout.decode("utf-8").strip()[1:])

    return ctr_names, ctr_ips

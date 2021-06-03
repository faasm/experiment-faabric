from os import remove
from os.path import dirname, realpath
from subprocess import check_output, run

PROJ_ROOT = dirname(dirname(realpath(__file__)))
SLOTS_PER_HOST = 4


def getContainers():
    docker_cmd = "docker-compose ps -aq"
    out = check_output(docker_cmd, shell=True, cwd=PROJ_ROOT).decode("utf-8")
    return " ".join(out.split("\n"))


def getIps():
    docker_cmd = "docker inspect -f '{{{{range.NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}}' {}".format(
        getContainers()
    )
    out = check_output(docker_cmd, shell=True, cwd=PROJ_ROOT).decode("utf-8")
    return out.split("\n")[:-1]


def copyFile(contents):
    # Open file
    with open("hostfile", "w+") as fh:
        fh.write(contents)
    # Copy contents
    container_name = "lammps-native_master_1"
    docker_cmd = "docker cp hostfile {}:/home/mpirun/hostfile".format(container_name)
    print(docker_cmd)
    run(docker_cmd, check=True, shell=True, cwd=PROJ_ROOT)
    remove("hostfile")

    # Cat the resulting file
    docker_cmd = "docker-compose exec --user mpirun master cat hostfile"
    print(docker_cmd)
    out = check_output(docker_cmd, shell=True, cwd=PROJ_ROOT).decode("utf-8")
    print(out)


def main():
    # Get container IPs
    ips = getIps()

    # Prepare file
    fileStr = "\n".join(["{} slots={}".format(i, SLOTS_PER_HOST) for i in ips])
    copyFile(fileStr)


if __name__ == "__main__":
    main()

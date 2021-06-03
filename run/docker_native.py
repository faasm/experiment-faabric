from os.path import dirname, realpath
from subprocess import run

PROJ_ROOT = dirname(dirname(realpath(__file__)))
EXPERIMENT_FILENAME = "run/all_native.py"
MASTER_CONTAINER_NAME = "lammps-native_master_1"


def copyFile():
    docker_cmd = "docker cp {} {}:/code/experiment-lammps/{}".format(
        EXPERIMENT_FILENAME, MASTER_CONTAINER_NAME, EXPERIMENT_FILENAME
    )
    print(docker_cmd)
    run(docker_cmd, shell=True, check=True, cwd=PROJ_ROOT)


def copyData(dataFile):
    docker_cmd = "docker cp {} {}:/data/{}".format(
        dataFile, MASTER_CONTAINER_NAME, dataFile
    )
    print(docker_cmd)
    run(docker_cmd, shell=True, check=True, cwd=PROJ_ROOT)


def runBenchmark():
    docker_cmd = "docker-compose exec --user mpirun master python3 /code/experiment-lammps/{}".format(
        EXPERIMENT_FILENAME
    )
    dataFile = "in.lj.hex"
    if (dataFile != ""):
        copyData(dataFile)
        docker_cmd += " /data/{}".format(dataFile)
    print(docker_cmd)
    run(docker_cmd, shell=True, check=True, cwd=PROJ_ROOT)


def copyResults():
    docker_cmd = "docker-compose exec --user mpirun master cat results.dat"
    print(docker_cmd)
    run(docker_cmd, shell=True, check=True, cwd=PROJ_ROOT)


def main():
    copyFile()

    runBenchmark()

    copyResults()


if __name__ == "__main__":
    main()

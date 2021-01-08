from os.path import join

from tasks.util.env import EXPERIMENT_ROOT

_version = None
_faasm_version = None


def get_version():
    global _version

    ver_file = join(EXPERIMENT_ROOT, "VERSION")

    if not _version:
        with open(ver_file, "r") as fh:
            _version = fh.read()
            _version = _version.strip()

        print("Read Experiment version: {}".format(_version))

    return _version


def get_faasm_version():
    global _faasm_version

    ver_file = join(EXPERIMENT_ROOT, ".env")

    if not _faasm_version:
        with open(ver_file, "r") as fh:
            _faasm_version = fh.readline()
            _faasm_version = _faasm_version.strip().split("=")[1]

    print("Read Faasm version: {}".format(_faasm_version))

    return _faasm_version

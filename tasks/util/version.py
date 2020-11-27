from os.path import join

from tasks.util.env import EXPERIMENT_ROOT

_version = None


def get_version():
    global _version

    ver_file = join(PROJ_ROOT, "VERSION")

    if not _version:
        with open(ver_file, "r") as fh:
            _version = fh.read()
            _version = _version.strip()

        print("Read Experiment version: {}".format(_version))

    return _version

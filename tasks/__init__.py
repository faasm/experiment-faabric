from invoke import Collection

from . import migration
from . import openmpi

import logging

from tasks.kernels import ns as kernels_ns
from tasks.lammps import ns as lammps_ns


logging.getLogger().setLevel(logging.DEBUG)

ns = Collection(
    migration,
    openmpi,
)

ns.add_collection(lammps_ns, name="lammps")
ns.add_collection(kernels_ns, name="kernels")

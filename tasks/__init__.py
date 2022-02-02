from invoke import Collection

from . import openmpi

import logging

from tasks.kernels import ns as kernels_ns
from tasks.lammps import ns as lammps_ns
from tasks.migration import ns as migration_ns


logging.getLogger().setLevel(logging.DEBUG)

ns = Collection(
    openmpi,
)

ns.add_collection(lammps_ns, name="lammps")
ns.add_collection(kernels_ns, name="kernels")
ns.add_collection(migration_ns, name="migration")

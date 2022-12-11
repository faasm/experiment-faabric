from invoke import Collection

from . import format_code
from . import openmpi

import logging

from tasks.kernels import ns as kernels_ns
from tasks.lammps import ns as lammps_ns
from tasks.makespan import ns as makespan_ns
from tasks.migration import ns as migration_ns
from tasks.mpi import ns as mpi_ns
from tasks.openmp import ns as openmp_ns


logging.getLogger().setLevel(logging.DEBUG)

ns = Collection(
    format_code,
    openmpi,
)

ns.add_collection(lammps_ns, name="lammps")
ns.add_collection(kernels_ns, name="kernels")
ns.add_collection(makespan_ns, name="makespan")
ns.add_collection(migration_ns, name="migration")
ns.add_collection(mpi_ns, name="mpi")
ns.add_collection(openmp_ns, name="openmp")

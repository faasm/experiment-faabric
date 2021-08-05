from invoke import Collection

from . import openmpi

from tasks.kernels import ns as kernels_ns
from tasks.lammps import ns as lammps_ns

ns = Collection(
    openmpi,
)

ns.add_collection(lammps_ns, name="lammps")
ns.add_collection(kernels_ns, name="kernels")

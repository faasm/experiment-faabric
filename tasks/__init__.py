from invoke import Collection

from . import container
from . import data
from . import mpi
from . import native
from . import run
from . import wasm

ns = Collection(
    container,
    data,
    mpi,
    native,
    run,
    wasm,
)

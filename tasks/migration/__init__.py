from invoke import Collection

from . import oracle
from . import plot
from . import run
from . import wasm

ns = Collection(oracle, plot, run, wasm)

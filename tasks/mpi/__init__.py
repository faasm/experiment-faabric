from invoke import Collection

from . import kernels
from . import plot
from . import run
from . import wasm

ns = Collection(kernels, plot, run, wasm)

from invoke import Collection

from . import native
from . import plot
from . import run
from . import wasm

ns = Collection(native, plot, run, wasm)

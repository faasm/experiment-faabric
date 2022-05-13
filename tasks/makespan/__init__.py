from invoke import Collection

from . import container
from . import native
from . import plot
from . import run
from . import trace
from . import wasm

ns = Collection(container, native, plot, run, trace, wasm)

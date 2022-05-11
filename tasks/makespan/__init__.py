from invoke import Collection

from . import native
from . import plot
from . import run
from . import trace

ns = Collection(native, plot, run, trace)

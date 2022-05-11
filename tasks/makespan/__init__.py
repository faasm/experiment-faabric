from invoke import Collection

from . import native
from . import plot
from . import run

ns = Collection(native, plot, run)

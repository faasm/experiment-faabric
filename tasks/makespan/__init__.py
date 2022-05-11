from invoke import Collection

from . import plot
from . import scheduler

ns = Collection(plot, scheduler)

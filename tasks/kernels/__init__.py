from invoke import Collection

from . import build
from . import container
from . import native
from . import run

ns = Collection(build, container, native, run)

from invoke import Collection

from . import build
from . import container
from . import native

ns = Collection(build, container, native)

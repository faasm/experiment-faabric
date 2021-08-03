from invoke import Collection

from . import container
from . import data
from . import native
from . import wasm

ns = Collection(
    container,
    data,
    native,
    wasm,
)

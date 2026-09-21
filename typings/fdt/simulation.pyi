from datetime import date

import numpy as np
from numpy.typing import NDArray

class RandomBundle:
    paths: int

class Simulation:
    dates: list[date]
    by_envelope: NDArray[np.int64]
    consumption: NDArray[np.int64]
    pending: NDArray[np.int64]

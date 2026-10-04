"""Named random streams from one SeedSequence per run (SIM_SPEC section 7).

The order of STREAMS is part of the common-random-numbers contract: adding a stream goes at
the end, so existing streams (and every cached failure world) keep their values.
"""

from __future__ import annotations

import numpy as np

STREAMS = ("failures", "placement", "arrivals", "lifetimes", "predictor", "policy")


class Streams:
    def __init__(self, seed: int):
        self.seed = int(seed)
        self._ss = dict(
            zip(STREAMS, np.random.SeedSequence(self.seed).spawn(len(STREAMS)), strict=True)
        )

    def gen(self, name: str, *key: int) -> np.random.Generator:
        """A fresh generator for stream `name`, optionally keyed (e.g. host id, life number).

        The same (seed, name, key) always gives the same generator, whatever was drawn before.
        """
        ss = self._ss[name]
        if key:
            ss = np.random.SeedSequence(ss.entropy, spawn_key=(*ss.spawn_key, *key))
        return np.random.default_rng(ss)

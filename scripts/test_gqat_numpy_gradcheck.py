"""
Task 11 -- numerical gradient check for gqat_net_numpy.py.

There's no framework to compare our hand-derived backward pass against, so
this is the verification step: pick a handful of parameters scattered across
every stage of the network (early conv, capsule, dual-attention, transformer,
dynamic conv, grouped-query attention, output), perturb each by +-eps,
re-run the forward pass to get the loss, and compare that central-difference
estimate against the analytic gradient our backward() computed. Run with
training=False everywhere so dropout's randomness doesn't add noise to the
comparison.
"""
import numpy as np
from gqat_net_numpy import GQATNetNumpy
from numpy_nn import numerical_gradient_check

rng = np.random.default_rng(0)
B, F = 6, 8
x = rng.normal(size=(B, F, 1))
y = rng.integers(0, 2, size=(B, 1)).astype(np.float64)

model = GQATNetNumpy(n_features=F, seed=123)

# Forward + backward once (training=False -> deterministic, no dropout mask noise)
model.forward(x, training=False)
model.backward(y)

def loss_fn():
    return model.loss(x, y, training=False)

checks = [
    ("conv3.W (early multi-scale conv)", model.conv3, "W"),
    ("gate3.W (early gate conv)", model.gate3, "W"),
    ("ln1.gamma (post-concat layernorm)", model.ln1, "gamma"),
    ("caps_conv.W (capsule projection)", model.caps_conv, "W"),
    ("dual_temp_score.W (temporal attention score)", model.dual_temp_score, "W"),
    ("dual_proj.W (dual-attention fusion)", model.dual_proj, "W"),
    ("t_q.W (transformer query)", model.t_q, "W"),
    ("ff2.W (transformer FFN)", model.ff2, "W"),
    ("dyn_dense.W (dynamic-conv gate)", model.dyn_dense, "W"),
    ("gqa_q0.W (grouped-query attention, group 0)", model.gqa_q[0], "W"),
    ("gqa_v1.W (grouped-query attention, group 1)", model.gqa_v[1], "W"),
    ("local_dense.W (local fusion)", model.local_dense, "W"),
    ("out_dense.W (output head)", model.out_dense, "W"),
    ("out_dense.b (output bias)", model.out_dense, "b"),
]

print(f"{'parameter':45s} {'max_rel_err':>12s}")
worst = 0.0
for name, layer, pname in checks:
    err = numerical_gradient_check(loss_fn, layer.params[pname], layer.grads[pname],
                                     eps=1e-4, n_samples=6, seed=1)
    worst = max(worst, err)
    flag = "  <-- CHECK" if err > 3e-2 else ""
    print(f"{name:45s} {err:12.6f}{flag}")

print(f"\nWorst max-relative-error across all checked parameters: {worst:.6f}")
print("PASS (gradients look correct)" if worst < 3e-2 else "FAIL (investigate the flagged layer(s))")

"""
Task 11 -- a tiny from-scratch NumPy neural-network toolkit.

Why this file exists: TensorFlow, PyTorch, Keras, and even lightweight
autodiff libraries (JAX, autograd) are all unavailable in this sandbox --
its package index is a locked-down allowlist that doesn't mirror any deep
learning framework (confirmed by trying all of them; see task11_summary.md).
NumPy + SciPy + scikit-learn ARE available, and NumPy alone is fully
sufficient to hand-write real forward/backward passes and train real
weights with gradient descent -- this is exactly how neural nets were
trained before frameworks existed. This module holds the small set of
reusable, hand-differentiated layers that gqat_net_numpy.py composes into
a GQAT-Net-inspired architecture.

Every layer below follows the same contract:
  - forward(x, training=True) -> y            (caches whatever backward needs)
  - backward(dy) -> dx                          (also fills self.grads[...])
  - .params  : dict[name -> ndarray]            (the learnable weights)
  - .grads   : dict[name -> ndarray]            (same keys, filled by backward)

so a generic Adam optimizer can walk any layer without knowing its internals.
"""
import numpy as np


def _rng(seed=None):
    return np.random.default_rng(seed)


# ---------------------------------------------------------------------------
# Parametrized layers
# ---------------------------------------------------------------------------
class Dense:
    """y = x @ W + b, applied over the last axis of an (..., in_dim) tensor."""

    def __init__(self, in_dim, out_dim, seed=None, scale=None):
        rng = _rng(seed)
        scale = scale or np.sqrt(2.0 / in_dim)  # He init (ReLU-friendly, fine for others too)
        self.params = {
            "W": rng.normal(0, scale, size=(in_dim, out_dim)).astype(np.float64),
            "b": np.zeros(out_dim, dtype=np.float64),
        }
        self.grads = {"W": None, "b": None}
        self._cache = None

    def clear_cache(self):
        self._cache = None

    def forward(self, x, training=True):
        self._cache = x
        return x @ self.params["W"] + self.params["b"]

    def backward(self, dy):
        x = self._cache
        # x: (..., in_dim), dy: (..., out_dim) -- flatten leading dims for the W/b grad sums
        flat_x = x.reshape(-1, x.shape[-1])
        flat_dy = dy.reshape(-1, dy.shape[-1])
        self.grads["W"] = flat_x.T @ flat_dy
        self.grads["b"] = flat_dy.sum(axis=0)
        return dy @ self.params["W"].T


class Conv1DSame:
    """1-D convolution, 'same' padding, stride 1, over (B, T, in_ch) -> (B, T, out_ch).

    Implemented as a sum of `kernel_size` shifted matmuls (kernel is tiny --
    3, 5, 7, or 1 in this project -- so this is both simple and fast, and
    avoids needing a general im2col routine)."""

    def __init__(self, in_ch, out_ch, kernel_size, seed=None):
        rng = _rng(seed)
        scale = np.sqrt(2.0 / (in_ch * kernel_size))
        self.k = kernel_size
        self.pad = kernel_size // 2
        self.params = {
            "W": rng.normal(0, scale, size=(kernel_size, in_ch, out_ch)).astype(np.float64),
            "b": np.zeros(out_ch, dtype=np.float64),
        }
        self.grads = {"W": None, "b": None}
        self._cache = None

    def clear_cache(self):
        self._cache = None

    def forward(self, x, training=True):
        B, T, _ = x.shape
        x_pad = np.pad(x, ((0, 0), (self.pad, self.pad), (0, 0)))
        self._cache = (x_pad, T)
        out = np.zeros((B, T, self.params["W"].shape[-1]), dtype=np.float64)
        for j in range(self.k):
            out += x_pad[:, j:j + T, :] @ self.params["W"][j]
        out += self.params["b"]
        return out

    def backward(self, dy):
        x_pad, T = self._cache
        dW = np.zeros_like(self.params["W"])
        dx_pad = np.zeros_like(x_pad)
        for j in range(self.k):
            seg = x_pad[:, j:j + T, :]
            dW[j] = np.einsum("bti,bto->io", seg, dy)
            dx_pad[:, j:j + T, :] += dy @ self.params["W"][j].T
        self.grads["W"] = dW
        self.grads["b"] = dy.reshape(-1, dy.shape[-1]).sum(axis=0)
        if self.pad:
            return dx_pad[:, self.pad:-self.pad, :]
        return dx_pad


class LayerNorm:
    """Standard layer norm over the last axis, with learnable gain/bias."""

    def __init__(self, dim, eps=1e-5):
        self.params = {"gamma": np.ones(dim), "beta": np.zeros(dim)}
        self.grads = {"gamma": None, "beta": None}
        self.eps = eps
        self._cache = None

    def clear_cache(self):
        self._cache = None

    def forward(self, x, training=True):
        mu = x.mean(axis=-1, keepdims=True)
        var = x.var(axis=-1, keepdims=True)
        std = np.sqrt(var + self.eps)
        xhat = (x - mu) / std
        self._cache = (xhat, std, x.shape[-1])
        return self.params["gamma"] * xhat + self.params["beta"]

    def backward(self, dy):
        xhat, std, n = self._cache
        gamma = self.params["gamma"]
        self.grads["gamma"] = np.reshape(dy * xhat, (-1, n)).sum(axis=0)
        self.grads["beta"] = np.reshape(dy, (-1, n)).sum(axis=0)
        dxhat = dy * gamma
        # standard layernorm backward formula
        dx = (1.0 / n) * (1.0 / std) * (
            n * dxhat
            - dxhat.sum(axis=-1, keepdims=True)
            - xhat * (dxhat * xhat).sum(axis=-1, keepdims=True)
        )
        return dx


class Dropout:
    def __init__(self, rate, seed=None):
        self.rate = rate
        self.rng = _rng(seed)
        self._mask = None

    def clear_cache(self):
        self._mask = None

    def forward(self, x, training=True):
        if not training or self.rate <= 0:
            self._mask = np.ones_like(x)
            return x
        keep = 1.0 - self.rate
        self._mask = (self.rng.random(x.shape) < keep).astype(x.dtype) / keep
        return x * self._mask

    def backward(self, dy):
        return dy * self._mask


# ---------------------------------------------------------------------------
# Stateless functional ops (with hand-derived backward)
# ---------------------------------------------------------------------------
class Sigmoid:
    def __init__(self):
        self._y = None

    def clear_cache(self):
        self._y = None

    def forward(self, x, training=True):
        self._y = 1.0 / (1.0 + np.exp(-np.clip(x, -60, 60)))
        return self._y

    def backward(self, dy):
        return dy * self._y * (1 - self._y)


class ReLU:
    def __init__(self):
        self._mask = None

    def clear_cache(self):
        self._mask = None

    def forward(self, x, training=True):
        self._mask = (x > 0).astype(x.dtype)
        return x * self._mask

    def backward(self, dy):
        return dy * self._mask


def softmax(x, axis=-1):
    x = x - x.max(axis=axis, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=axis, keepdims=True)


def softmax_backward(dy, s, axis=-1):
    """Vector-Jacobian product for softmax, s = softmax(x) (forward output)."""
    dot = (dy * s).sum(axis=axis, keepdims=True)
    return s * (dy - dot)


def squash(s, axis=-1, eps=1e-8):
    """Capsule-style squashing nonlinearity: unit-ish vectors, small ones shrunk to ~0."""
    sq_norm = np.sum(s ** 2, axis=axis, keepdims=True)
    scale = sq_norm / (1.0 + sq_norm)
    unit = s / np.sqrt(sq_norm + eps)
    return scale * unit


def squash_backward(dy, s, axis=-1, eps=1e-8):
    """Numerically-stable backward for squash via finite-difference-free chain rule.

    v = (||s||^2 / (1+||s||^2)) * s / ||s||  =  f(n) * s / sqrt(n)   where n = ||s||^2
    dv/ds_i = f(n) * (delta_ij / sqrt(n) - s_i*s_j / n^{1.5}) + s_i/sqrt(n) * f'(n) * 2*s_j
    Implemented via the two scalar-per-vector coefficients below (no explicit Jacobian
    matrix is formed -- it's contracted analytically against dy directly).
    """
    n = np.sum(s ** 2, axis=axis, keepdims=True) + eps
    sqrt_n = np.sqrt(n)
    f = n / (1.0 + n)          # scalar per vector
    fprime = 2.0 / (1.0 + n) ** 2  # d f/d n

    dy_dot_s = np.sum(dy * s, axis=axis, keepdims=True)
    dy_sum = np.sum(dy, axis=axis, keepdims=True)  # unused directly; kept for clarity

    term1 = (f / sqrt_n) * dy
    term2 = -(f / (n * sqrt_n)) * dy_dot_s * s
    term3 = (fprime / sqrt_n) * dy_dot_s * s
    return term1 + term2 + term3


# ---------------------------------------------------------------------------
# Adam optimizer -- generic over any collection of {layer_key: layer} pairs
# ---------------------------------------------------------------------------
class Adam:
    def __init__(self, layers, lr=1e-3, beta1=0.9, beta2=0.999, eps=1e-8):
        self.layers = layers  # dict: name -> layer object with .params/.grads
        self.lr = lr
        self.b1, self.b2, self.eps = beta1, beta2, eps
        self.t = 0
        self.m, self.v = {}, {}
        for lname, layer in layers.items():
            for pname in getattr(layer, "params", {}):
                key = f"{lname}.{pname}"
                self.m[key] = np.zeros_like(layer.params[pname])
                self.v[key] = np.zeros_like(layer.params[pname])

    def step(self):
        self.t += 1
        for lname, layer in self.layers.items():
            if not hasattr(layer, "params"):
                continue
            for pname in layer.params:
                g = layer.grads.get(pname)
                if g is None:
                    continue
                key = f"{lname}.{pname}"
                self.m[key] = self.b1 * self.m[key] + (1 - self.b1) * g
                self.v[key] = self.b2 * self.v[key] + (1 - self.b2) * (g ** 2)
                mhat = self.m[key] / (1 - self.b1 ** self.t)
                vhat = self.v[key] / (1 - self.b2 ** self.t)
                layer.params[pname] -= self.lr * mhat / (np.sqrt(vhat) + self.eps)


# ---------------------------------------------------------------------------
# Numerical gradient check -- the closest thing to a unit test we have
# without an autodiff framework to compare against.
# ---------------------------------------------------------------------------
def numerical_gradient_check(loss_fn, param, grad, eps=1e-4, n_samples=8, seed=0):
    """Spot-checks `grad` (analytic) against central finite differences of
    `loss_fn()` (which must re-run the *whole* forward pass and return a
    scalar loss) at `n_samples` random entries of `param`. Returns the max
    relative error found."""
    rng = _rng(seed)
    flat_idx = rng.choice(param.size, size=min(n_samples, param.size), replace=False)
    flat = param.reshape(-1)
    grad_flat = grad.reshape(-1)
    max_rel_err = 0.0
    for idx in flat_idx:
        orig = flat[idx]
        flat[idx] = orig + eps
        loss_plus = loss_fn()
        flat[idx] = orig - eps
        loss_minus = loss_fn()
        flat[idx] = orig
        numeric = (loss_plus - loss_minus) / (2 * eps)
        analytic = grad_flat[idx]
        rel_err = abs(numeric - analytic) / max(1e-8, abs(numeric) + abs(analytic))
        max_rel_err = max(max_rel_err, rel_err)
    return max_rel_err

"""
Task 11 -- a from-scratch NumPy re-implementation of GQAT-Net's architectural
ideas (Tripathi et al., "GQAT-Net: A Calibrated Attention Model for Failure
Prediction in Large-Scale Distributed Systems," J. Grid Computing 2025,
https://github.com/tri-shi/GQAT-NET), adapted to this project's Backblaze
hazard features.

This is NOT a port of the paper's Keras code (TensorFlow/PyTorch/Keras/JAX
are all unavailable in this sandbox -- see task11_summary.md for how that was
confirmed). It is a real, independently hand-written and hand-differentiated
neural network built only on top of numpy_nn.py's primitives, that keeps
every one of the original architecture's named sub-blocks:

  input -> multi-scale gated convolutions (k=3,5,7) -> LayerNorm
        -> temporal capsules (squash nonlinearity)
        -> dual (temporal + spatial) attention, residual fusion
        -> a transformer self-attention block
        -> a dynamic, globally-modulated 1x1 conv
        -> dropout (standard, in place of the paper's block-structured DropBlock)
        -> grouped-query self-attention  <- the model's namesake block
        -> global+local fusion -> sigmoid output

Channel widths are scaled down (16-48 instead of 64-256) relative to the
original, since this project's engineered feature vector is a ~10-element
row rather than the paper's much larger cluster-trace feature set, and
training runs on 2 CPU cores with hand-written (non-BLAS-fused) backprop
bookkeeping -- see task11_summary.md for the full reasoning.
"""
import numpy as np

from numpy_nn import (
    Dense, Conv1DSame, LayerNorm, Dropout, Sigmoid, ReLU,
    softmax, softmax_backward, squash, squash_backward, Adam,
)


def _concat_backward(dcat, sizes, axis=-1):
    """Split a gradient for a concat() back into per-input pieces."""
    parts, start = [], 0
    for s in sizes:
        sl = [slice(None)] * dcat.ndim
        sl[axis] = slice(start, start + s)
        parts.append(dcat[tuple(sl)])
        start += s
    return parts


def _split_heads(x, num_heads):
    B, F, C = x.shape
    Dh = C // num_heads
    return x.reshape(B, F, num_heads, Dh).transpose(0, 2, 1, 3)  # (B,H,F,Dh)


def _merge_heads(x):
    B, H, F, Dh = x.shape
    return x.transpose(0, 2, 1, 3).reshape(B, F, H * Dh)


def _attn_forward(q, k, v):
    """Scaled dot-product attention over the last two axes of (..., F, D)."""
    d = q.shape[-1]
    logits = np.matmul(q, np.swapaxes(k, -1, -2)) / np.sqrt(d)
    w = softmax(logits, axis=-1)
    out = np.matmul(w, v)
    return out, (q, k, v, w, d)


def _attn_backward(dout, cache):
    q, k, v, w, d = cache
    dv = np.matmul(np.swapaxes(w, -1, -2), dout)
    dw = np.matmul(dout, np.swapaxes(v, -1, -2))
    dlogits = softmax_backward(dw, w, axis=-1) / np.sqrt(d)
    dq = np.matmul(dlogits, k)
    dk = np.matmul(np.swapaxes(dlogits, -1, -2), q)
    return dq, dk, dv


class GQATNetNumpy:
    def __init__(self, n_features, seed=42, gqa_groups=2, dropout_rate=0.1,
                 feat_dropout_rate=0.3):
        rng_seed = seed
        self.F = n_features
        C1 = 16                      # per-branch multi-scale conv channels
        CAT = 3 * C1                 # 48 after concatenating the 3 branches
        CAPS_GROUPS, CAPS_DIM = 4, 8
        CAPS = CAPS_GROUPS * CAPS_DIM  # 32
        TRANS_HEADS = 2
        DYN = 16
        self.caps_groups, self.caps_dim = CAPS_GROUPS, CAPS_DIM
        self.trans_heads = TRANS_HEADS
        self.gqa_groups = gqa_groups
        self.gqa_group_size = DYN // gqa_groups

        s = rng_seed
        # -- multi-scale gated convs --
        self.conv3, self.gate3 = Conv1DSame(1, C1, 3, seed=s + 1), Conv1DSame(1, C1, 3, seed=s + 2)
        self.conv5, self.gate5 = Conv1DSame(1, C1, 5, seed=s + 3), Conv1DSame(1, C1, 5, seed=s + 4)
        self.conv7, self.gate7 = Conv1DSame(1, C1, 7, seed=s + 5), Conv1DSame(1, C1, 7, seed=s + 6)
        self.sig_g3, self.sig_g5, self.sig_g7 = Sigmoid(), Sigmoid(), Sigmoid()
        self.ln1 = LayerNorm(CAT)

        # -- temporal capsules --
        self.caps_conv = Conv1DSame(CAT, CAPS, 1, seed=s + 7)

        # -- dual attention --
        self.dual_temp_score = Dense(CAPS, 1, seed=s + 8)
        self.dual_spatial_gate = Dense(CAPS, CAPS, seed=s + 9)
        self.sig_spatial = Sigmoid()
        self.dual_proj = Dense(2 * CAPS, CAPS, seed=s + 10)

        # -- transformer block --
        self.t_q = Dense(CAPS, CAPS, seed=s + 11)
        self.t_k = Dense(CAPS, CAPS, seed=s + 12)
        self.t_v = Dense(CAPS, CAPS, seed=s + 13)
        self.t_out = Dense(CAPS, CAPS, seed=s + 14)
        self.ln_attn = LayerNorm(CAPS)
        self.ff1 = Dense(CAPS, 2 * CAPS, seed=s + 15)
        self.relu_ff = ReLU()
        self.ff2 = Dense(2 * CAPS, CAPS, seed=s + 16)
        self.ln_ff = LayerNorm(CAPS)

        # -- dynamic conv --
        self.dyn_dense = Dense(CAPS, DYN, seed=s + 17)
        self.relu_dyn_gate = ReLU()
        self.dyn_conv = Conv1DSame(CAPS, DYN, 1, seed=s + 18)
        self.relu_dyn_conv = ReLU()

        self.dropout_db = Dropout(dropout_rate, seed=s + 19)

        # -- grouped query attention (the model's namesake block) --
        gs = self.gqa_group_size
        self.gqa_q = [Dense(gs, gs, seed=s + 20 + i) for i in range(gqa_groups)]
        self.gqa_k = [Dense(gs, gs, seed=s + 30 + i) for i in range(gqa_groups)]
        self.gqa_v = [Dense(gs, gs, seed=s + 40 + i) for i in range(gqa_groups)]

        # -- global+local fusion + output --
        self.local_dense = Dense(DYN, DYN, seed=s + 50)
        self.relu_local = ReLU()
        self.dropout_feat = Dropout(feat_dropout_rate, seed=s + 51)
        self.out_dense = Dense(2 * DYN, 1, seed=s + 52)

        self._layers = self._collect_layers()

    def _collect_layers(self):
        layers = {
            "conv3": self.conv3, "gate3": self.gate3, "conv5": self.conv5, "gate5": self.gate5,
            "conv7": self.conv7, "gate7": self.gate7, "ln1": self.ln1, "caps_conv": self.caps_conv,
            "dual_temp_score": self.dual_temp_score, "dual_spatial_gate": self.dual_spatial_gate,
            "dual_proj": self.dual_proj, "t_q": self.t_q, "t_k": self.t_k, "t_v": self.t_v,
            "t_out": self.t_out, "ln_attn": self.ln_attn, "ff1": self.ff1, "ff2": self.ff2,
            "ln_ff": self.ln_ff, "dyn_dense": self.dyn_dense, "dyn_conv": self.dyn_conv,
            "local_dense": self.local_dense, "out_dense": self.out_dense,
        }
        for i, l in enumerate(self.gqa_q):
            layers[f"gqa_q{i}"] = l
        for i, l in enumerate(self.gqa_k):
            layers[f"gqa_k{i}"] = l
        for i, l in enumerate(self.gqa_v):
            layers[f"gqa_v{i}"] = l
        return layers

    # ------------------------------------------------------------------
    def forward(self, x, training=True, mc_dropout=False):
        """x: (B, F, 1) -> p: (B,1) predicted probability. Caches everything
        backward() needs in self.c."""
        c = {}
        c["x"] = x

        c3 = self.conv3.forward(x, training); g3p = self.gate3.forward(x, training); g3 = self.sig_g3.forward(g3p, training)
        gc1 = c3 * g3
        c5 = self.conv5.forward(x, training); g5p = self.gate5.forward(x, training); g5 = self.sig_g5.forward(g5p, training)
        gc2 = c5 * g5
        c7 = self.conv7.forward(x, training); g7p = self.gate7.forward(x, training); g7 = self.sig_g7.forward(g7p, training)
        gc3_ = c7 * g7
        c.update(c3=c3, g3=g3, c5=c5, g5=g5, c7=c7, g7=g7)

        concat_x = np.concatenate([gc1, gc2, gc3_], axis=-1)
        c["concat_sizes"] = [gc1.shape[-1], gc2.shape[-1], gc3_.shape[-1]]
        x_ln1 = self.ln1.forward(concat_x, training)

        caps_pre = self.caps_conv.forward(x_ln1, training)
        B, F, _ = caps_pre.shape
        caps_pre_r = caps_pre.reshape(B, F, self.caps_groups, self.caps_dim)
        x_caps_r = squash(caps_pre_r, axis=-1)
        x_caps = x_caps_r.reshape(B, F, self.caps_groups * self.caps_dim)
        c["caps_pre_r"] = caps_pre_r
        c["x_caps"] = x_caps

        score = self.dual_temp_score.forward(x_caps, training)          # (B,F,1)
        alpha = softmax(score, axis=1)
        attn_temp = np.sum(alpha * x_caps, axis=1)                      # (B,CAPS)
        g_mean = x_caps.mean(axis=1)
        spatial_pre = self.dual_spatial_gate.forward(g_mean, training)
        beta = self.sig_spatial.forward(spatial_pre, training)
        attn_spat = beta * g_mean
        fused = np.concatenate([attn_temp, attn_spat], axis=-1)
        proj = self.dual_proj.forward(fused, training)                  # (B,CAPS)
        proj_tiled = np.repeat(proj[:, None, :], F, axis=1)
        x_res = x_caps + proj_tiled
        c.update(alpha=alpha, attn_temp=attn_temp, g_mean=g_mean, beta=beta,
                  attn_spat=attn_spat, proj=proj, F=F, B=B)

        q = self.t_q.forward(x_res, training); k = self.t_k.forward(x_res, training); v = self.t_v.forward(x_res, training)
        qh, kh, vh = _split_heads(q, self.trans_heads), _split_heads(k, self.trans_heads), _split_heads(v, self.trans_heads)
        attn_out_h, attn_cache = _attn_forward(qh, kh, vh)
        attn_out = _merge_heads(attn_out_h)
        attn_proj = self.t_out.forward(attn_out, training)
        x_ln_attn_in = x_res + attn_proj
        x_ln_attn = self.ln_attn.forward(x_ln_attn_in, training)
        ff_h_pre = self.ff1.forward(x_ln_attn, training)
        ff_h = self.relu_ff.forward(ff_h_pre, training)
        ff_out = self.ff2.forward(ff_h, training)
        x_ln_ff_in = x_ln_attn + ff_out
        x_trans = self.ln_ff.forward(x_ln_ff_in, training)
        c.update(x_res=x_res, attn_cache=attn_cache, x_ln_attn=x_ln_attn)

        gctx = x_trans.mean(axis=1)
        dyn_pre = self.dyn_dense.forward(gctx, training)
        dyn_w = self.relu_dyn_gate.forward(dyn_pre, training)
        xdyn_pre = self.dyn_conv.forward(x_trans, training)
        x_dyn_relu = self.relu_dyn_conv.forward(xdyn_pre, training)
        x_dyn = x_dyn_relu * dyn_w[:, None, :]
        c.update(x_trans=x_trans, dyn_w=dyn_w, x_dyn_relu=x_dyn_relu)

        do_train = training or mc_dropout
        x_db = self.dropout_db.forward(x_dyn, training=do_train)

        gs = self.gqa_group_size
        outs = []
        gqa_caches = []
        for i in range(self.gqa_groups):
            xi = x_db[:, :, i * gs:(i + 1) * gs]
            qi = self.gqa_q[i].forward(xi, training)
            ki = self.gqa_k[i].forward(xi, training)
            vi = self.gqa_v[i].forward(xi, training)
            oi, cache_i = _attn_forward(qi, ki, vi)
            outs.append(oi)
            gqa_caches.append(cache_i)
        x_gqa = np.concatenate(outs, axis=-1)
        c["gqa_caches"] = gqa_caches

        g_global = x_gqa.mean(axis=1)
        local_pre = self.local_dense.forward(x_gqa, training)
        g_local_full = self.relu_local.forward(local_pre, training)
        g_local = g_local_full.mean(axis=1)
        feat = np.concatenate([g_global, g_local], axis=-1)
        feat_drop = self.dropout_feat.forward(feat, training=do_train)
        c.update(x_gqa=x_gqa, g_local_full=g_local_full)

        logits = self.out_dense.forward(feat_drop, training)
        p = 1.0 / (1.0 + np.exp(-np.clip(logits, -60, 60)))
        c["p"] = p
        self.c = c
        return p

    # ------------------------------------------------------------------
    def backward(self, y):
        """y: (B,1) true labels. Computes dL/dparams for every layer via
        binary cross-entropy on the cached forward pass's output."""
        c = self.c
        p, B, F = c["p"], c["B"], c["F"]
        dlogits = (p - y) / B  # combined BCE+sigmoid gradient

        dfeat_drop = self.out_dense.backward(dlogits)
        dfeat = self.dropout_feat.backward(dfeat_drop)
        dg_global, dg_local = _concat_backward(dfeat, [dfeat.shape[-1] // 2, dfeat.shape[-1] // 2])

        dg_local_full = np.repeat(dg_local[:, None, :], F, axis=1) / F
        dlocal_pre = self.relu_local.backward(dg_local_full)
        dx_gqa_from_local = self.local_dense.backward(dlocal_pre)
        dx_gqa_from_global = np.repeat(dg_global[:, None, :], F, axis=1) / F
        dx_gqa = dx_gqa_from_local + dx_gqa_from_global

        gs = self.gqa_group_size
        dx_db_parts = []
        gqa_caches = c["gqa_caches"]
        d_parts = _concat_backward(dx_gqa, [gs] * self.gqa_groups)
        for i in range(self.gqa_groups):
            doi = d_parts[i]
            dqi, dki, dvi = _attn_backward(doi, gqa_caches[i])
            dxi_q = self.gqa_q[i].backward(dqi)
            dxi_k = self.gqa_k[i].backward(dki)
            dxi_v = self.gqa_v[i].backward(dvi)
            dx_db_parts.append(dxi_q + dxi_k + dxi_v)
        dx_db = np.concatenate(dx_db_parts, axis=-1)

        dx_dyn = self.dropout_db.backward(dx_db)
        dx_dyn_relu = dx_dyn * c["dyn_w"][:, None, :]
        ddyn_w = np.sum(dx_dyn * c["x_dyn_relu"], axis=1)
        dxdyn_pre = self.relu_dyn_conv.backward(dx_dyn_relu)
        dx_trans_from_dynconv = self.dyn_conv.backward(dxdyn_pre)
        ddyn_pre = self.relu_dyn_gate.backward(ddyn_w)
        dgctx = self.dyn_dense.backward(ddyn_pre)
        dx_trans_from_gctx = np.repeat(dgctx[:, None, :], F, axis=1) / F
        dx_trans = dx_trans_from_dynconv + dx_trans_from_gctx

        dx_ln_ff_in = self.ln_ff.backward(dx_trans)
        dx_ln_attn_from_res = dx_ln_ff_in  # residual identity branch
        dff_out = dx_ln_ff_in
        dff_h = self.ff2.backward(dff_out)
        dff_h_pre = self.relu_ff.backward(dff_h)
        dx_ln_attn_from_ff = self.ff1.backward(dff_h_pre)
        dx_ln_attn = dx_ln_attn_from_res + dx_ln_attn_from_ff

        dx_ln_attn_in = self.ln_attn.backward(dx_ln_attn)
        dx_res_from_attnres = dx_ln_attn_in
        dattn_proj = dx_ln_attn_in
        dattn_out = self.t_out.backward(dattn_proj)
        dattn_out_h = _split_heads(dattn_out, self.trans_heads)
        dqh, dkh, dvh = _attn_backward(dattn_out_h, c["attn_cache"])
        dq, dk, dv = _merge_heads(dqh), _merge_heads(dkh), _merge_heads(dvh)
        dx_res_from_q = self.t_q.backward(dq)
        dx_res_from_k = self.t_k.backward(dk)
        dx_res_from_v = self.t_v.backward(dv)
        dx_res = dx_res_from_attnres + dx_res_from_q + dx_res_from_k + dx_res_from_v

        dx_caps_from_res = dx_res
        dproj_tiled = dx_res
        dproj = dproj_tiled.sum(axis=1)
        dfused = self.dual_proj.backward(dproj)
        dattn_temp, dattn_spat = _concat_backward(dfused, [dfused.shape[-1] // 2, dfused.shape[-1] // 2])

        dbeta = dattn_spat * c["g_mean"]
        dg_mean_from_spat = dattn_spat * c["beta"]
        dspatial_pre = self.sig_spatial.backward(dbeta)
        dg_mean_from_gate = self.dual_spatial_gate.backward(dspatial_pre)
        dg_mean = dg_mean_from_spat + dg_mean_from_gate
        dx_caps_from_gmean = np.repeat(dg_mean[:, None, :], F, axis=1) / F

        dalpha = dattn_temp[:, None, :] * c["x_caps"]
        dx_caps_from_attntemp_direct = c["alpha"] * dattn_temp[:, None, :]
        dscore = softmax_backward(dalpha.sum(axis=-1, keepdims=True), c["alpha"], axis=1)
        dx_caps_from_score = self.dual_temp_score.backward(dscore)

        dx_caps = (dx_caps_from_res + dx_caps_from_gmean
                   + dx_caps_from_attntemp_direct + dx_caps_from_score)

        B_, F_, _, _ = c["caps_pre_r"].shape
        dx_caps_r = dx_caps.reshape(B_, F_, self.caps_groups, self.caps_dim)
        dcaps_pre_r = squash_backward(dx_caps_r, c["caps_pre_r"], axis=-1)
        dcaps_pre = dcaps_pre_r.reshape(B_, F_, self.caps_groups * self.caps_dim)
        dx_ln1 = self.caps_conv.backward(dcaps_pre)

        dconcat_x = self.ln1.backward(dx_ln1)
        dgc1, dgc2, dgc3 = _concat_backward(dconcat_x, c["concat_sizes"])

        dc3 = dgc1 * c["g3"]; dg3 = dgc1 * c["c3"]
        dc5 = dgc2 * c["g5"]; dg5 = dgc2 * c["c5"]
        dc7 = dgc3 * c["g7"]; dg7 = dgc3 * c["c7"]

        dx = self.conv3.backward(dc3)
        dg3p = self.sig_g3.backward(dg3); dx = dx + self.gate3.backward(dg3p)
        dx = dx + self.conv5.backward(dc5)
        dg5p = self.sig_g5.backward(dg5); dx = dx + self.gate5.backward(dg5p)
        dx = dx + self.conv7.backward(dc7)
        dg7p = self.sig_g7.backward(dg7); dx = dx + self.gate7.backward(dg7p)
        return dx  # gradient w.r.t. the input (unused, but returned for completeness)

    # ------------------------------------------------------------------
    def loss(self, x, y, training=True):
        p = self.forward(x, training=training)
        eps = 1e-9
        return float(-np.mean(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)))

    def clear_cache(self):
        """Drop every cached forward-pass activation -- both this class's own
        self.c dict AND each individual layer/activation's internal cache
        (Dense/Conv1DSame/LayerNorm's self._cache, Dropout's self._mask,
        Sigmoid's self._y, ReLU's self._mask). These are only needed between
        a forward() and the immediately-following backward() call; leaving
        them attached afterward (e.g. before pickling the model) silently
        bloats the saved file by tens-to-hundreds of MB, sized to whatever
        batch happened to run most recently -- exactly the bug that first
        produced a 200MB+ .joblib file for what is actually a few-thousand-
        parameter model."""
        self.c = {}
        for layer in self._layers.values():
            if hasattr(layer, "clear_cache"):
                layer.clear_cache()
        for act in (self.sig_g3, self.sig_g5, self.sig_g7, self.sig_spatial,
                    self.relu_ff, self.relu_dyn_gate, self.relu_dyn_conv, self.relu_local,
                    self.dropout_db, self.dropout_feat):
            act.clear_cache()

    def predict_proba(self, X):
        x = X.reshape(X.shape[0], X.shape[1], 1).astype(np.float64)
        return self.forward(x, training=False).ravel()

    def predict_proba_mc(self, X, n_iter=20):
        x = X.reshape(X.shape[0], X.shape[1], 1).astype(np.float64)
        preds = np.stack([self.forward(x, training=False, mc_dropout=True).ravel()
                           for _ in range(n_iter)], axis=0)
        return preds.mean(axis=0), preds.std(axis=0)

    def fit(self, X, y, epochs=15, batch_size=512, lr=1e-3, X_val=None, y_val=None,
            patience=4, seed=0, verbose=True):
        rng = np.random.default_rng(seed)
        opt = Adam(self._layers, lr=lr)
        n = X.shape[0]
        y = y.reshape(-1, 1).astype(np.float64)
        if y_val is not None:
            y_val = y_val.reshape(-1, 1).astype(np.float64)
        best_val, best_state, bad_epochs = np.inf, None, 0
        history = []
        for epoch in range(1, epochs + 1):
            idx = rng.permutation(n)
            epoch_loss = 0.0
            n_batches = 0
            for start in range(0, n, batch_size):
                bidx = idx[start:start + batch_size]
                xb = X[bidx].reshape(len(bidx), X.shape[1], 1).astype(np.float64)
                yb = y[bidx]
                p = self.forward(xb, training=True)
                eps = 1e-9
                epoch_loss += float(-np.mean(yb * np.log(p + eps) + (1 - yb) * np.log(1 - p + eps)))
                n_batches += 1
                self.backward(yb)
                opt.step()
            epoch_loss /= max(1, n_batches)
            val_loss = None
            if X_val is not None:
                p_val = self.predict_proba(X_val)
                eps = 1e-9
                val_loss = float(-np.mean(y_val.ravel() * np.log(p_val + eps)
                                           + (1 - y_val.ravel()) * np.log(1 - p_val + eps)))
                if val_loss < best_val - 1e-5:
                    best_val, bad_epochs = val_loss, 0
                else:
                    bad_epochs += 1
            history.append((epoch, epoch_loss, val_loss))
            if verbose:
                msg = f"epoch {epoch:2d}/{epochs}  train_loss={epoch_loss:.5f}"
                if val_loss is not None:
                    msg += f"  val_loss={val_loss:.5f}"
                print(msg)
            if X_val is not None and bad_epochs >= patience:
                if verbose:
                    print(f"early stopping at epoch {epoch} (no val improvement for {patience} epochs)")
                break
        return history

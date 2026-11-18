"""SHAP explanation panel for PhaseWise AI.

Renders an expandable 'Why this prediction?' waterfall chart
for both the network-work (classifier) and duration (regressor) models.
"""

from __future__ import annotations

import html as _html
from typing import Any

import streamlit as st

from dashboard.ui import callout


# ---------------------------------------------------------------------------
# Model loading (cached)
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def _load_nw_model():
    """Load the network-work logistic-regression pipeline."""
    from pathlib import Path
    from modeling.model_registry import load_model
    from config import config
    model_path = Path(config.NETWORK_WORK_MODEL_FILE)
    if not model_path.exists():
        return None
    return load_model(str(model_path))


@st.cache_resource(show_spinner=False)
def _load_dur_model():
    """Load the duration random-forest pipeline."""
    from pathlib import Path
    from modeling.model_registry import load_model
    from config import config
    model_path = Path(config.DURATION_MODEL_FILE)
    if not model_path.exists():
        return None
    return load_model(str(model_path))


# ---------------------------------------------------------------------------
# Feature-row builder
# ---------------------------------------------------------------------------

def _build_feature_row(application: dict, numeric_cols: list, categorical_cols: list) -> "pd.DataFrame":
    """Create a one-row DataFrame aligned to the model's feature schema."""
    import pandas as pd
    row: dict[str, Any] = {}
    for col in numeric_cols:
        raw = application.get(col)
        try:
            row[col] = float(raw) if raw not in (None, "") else 0.0
        except (TypeError, ValueError):
            row[col] = 0.0
    for col in categorical_cols:
        raw = application.get(col)
        row[col] = str(raw) if raw not in (None, "") else None  # let imputer fill
    return pd.DataFrame([row])


# ---------------------------------------------------------------------------
# Waterfall HTML chart
# ---------------------------------------------------------------------------

def _render_feature_rows(
    feature_names: list[str],
    feature_values: list[Any],
    shap_values: list[float],
    base_value: float,
    prediction: float,
    title: str,
    unit: str = "",
) -> None:
    """Render a clean, evenly spaced waterfall panel in Streamlit columns."""
    top_n = 8
    pairs = sorted(
        zip(feature_names, feature_values, shap_values),
        key=lambda x: abs(x[2]),
        reverse=True,
    )[:top_n]
    if not pairs:
        return

    max_abs = max((abs(s) for _, _, s in pairs), default=1.0) or 1.0

    st.markdown(
        f'<div style="font-size:13.5px;font-weight:700;color:var(--pw-ink,#16201D);margin-bottom:6px">{_html.escape(title)}</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        f"Base value: {base_value:.4f}{unit} → Prediction: {prediction:.4f}{unit}"
    )
    legend = st.columns(2)
    with legend[0]:
        st.markdown(
            '<div style="display:flex;align-items:center;gap:8px;color:var(--pw-muted);font-size:11px"><span style="width:10px;height:10px;border-radius:3px;background:#16a34a;display:inline-block"></span>Increases prediction</div>',
            unsafe_allow_html=True,
        )
    with legend[1]:
        st.markdown(
            '<div style="display:flex;align-items:center;gap:8px;color:var(--pw-muted);font-size:11px"><span style="width:10px;height:10px;border-radius:3px;background:#dc2626;display:inline-block"></span>Decreases prediction</div>',
            unsafe_allow_html=True,
        )

    header = st.columns([1.7, 3.2, 0.8, 0.9])
    header[0].markdown('<div style="font-size:11px;color:var(--pw-muted);font-weight:600;text-transform:uppercase;letter-spacing:0.04em">Feature</div>', unsafe_allow_html=True)
    header[1].markdown('<div style="font-size:11px;color:var(--pw-muted);font-weight:600;text-transform:uppercase;letter-spacing:0.04em">Contribution</div>', unsafe_allow_html=True)
    header[2].markdown('<div style="font-size:11px;color:var(--pw-muted);font-weight:600;text-align:right;text-transform:uppercase;letter-spacing:0.04em">SHAP</div>', unsafe_allow_html=True)
    header[3].markdown('<div style="font-size:11px;color:var(--pw-muted);font-weight:600;text-align:right;text-transform:uppercase;letter-spacing:0.04em">Value</div>', unsafe_allow_html=True)

    for feat_name, feat_val, shap_val in pairs:
        raw_name = str(feat_name).split("__")[-1].replace("_", " ").title()
        display_value = str(feat_val)
        color = "#16a34a" if shap_val >= 0 else "#dc2626"
        width = max(8.0, abs(shap_val) / max_abs * 100.0)
        if not width.is_finite():
            width = 8.0
        signed_value = f"{shap_val:+.4f}"
        left_pct = 50.0 if shap_val >= 0 else max(0.0, 100.0 - width)

        c_name, c_bar, c_amount, c_actual = st.columns([1.7, 3.2, 0.8, 0.9])
        with c_name:
            st.caption(raw_name, help=f"{display_value}")
        with c_bar:
            bar_left = 50.0 if shap_val >= 0 else 50.0 - width / 2.0
            bar_width = max(width, 8.0)
            st.markdown(
                f'<div style="height:12px;border-radius:999px;background:rgba(16,24,22,0.06);'
                f'position:relative;overflow:hidden;border:1px solid rgba(16,24,22,0.04);">'
                f'<div style="position:absolute;top:0;bottom:0;left:{bar_left:.1f}%;width:{bar_width:.1f}%;'
                f'background:{color};border-radius:999px;opacity:0.9;"></div></div>',
                unsafe_allow_html=True,
            )
        with c_amount:
            st.markdown(
                f'<div style="text-align:right;color:{color};font-weight:700;font-size:11.5px;'
                f'font-family:var(--pw-font-mono, monospace)">{_html.escape(signed_value)}</div>',
                unsafe_allow_html=True,
            )
        with c_actual:
            st.markdown(
                f'<div style="text-align:right;color:var(--pw-muted,#6A7471);font-size:11px;'
                f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{_html.escape(display_value[:12])}</div>',
                unsafe_allow_html=True,
            )

    st.caption(f"Top {len(pairs)} features by |SHAP value|. Longer bars mean more influence.")


# ---------------------------------------------------------------------------
# SHAP computation helpers
# ---------------------------------------------------------------------------

def _shap_classifier(model, row_df: "pd.DataFrame") -> tuple[list, list, list, float, float]:
    """Return (names, values, shap_vals, base_val, prediction) for the classifier."""
    import numpy as np
    import shap
    from config import config

    preprocessor = model.named_steps[config.PREPROCESSING_STEP_NAME]
    estimator = model.named_steps[config.MODEL_STEP_NAME]

    X_transformed = preprocessor.transform(row_df)
    try:
        feature_names_out = list(preprocessor.get_feature_names_out())
    except Exception:
        feature_names_out = [f"f{i}" for i in range(X_transformed.shape[1])]

    explainer = shap.LinearExplainer(estimator, X_transformed)
    shap_vals = explainer.shap_values(X_transformed)

    # Binary classification: may return list of [neg_class, pos_class]
    if isinstance(shap_vals, list):
        sv = shap_vals[1] if len(shap_vals) > 1 else shap_vals[0]
    else:
        sv = shap_vals
    shap_row = sv[0].tolist() if hasattr(sv[0], "tolist") else list(sv[0])

    base_val_raw = explainer.expected_value
    if isinstance(base_val_raw, (list, np.ndarray)):
        base_val = float(base_val_raw[1]) if len(base_val_raw) > 1 else float(base_val_raw[0])
    else:
        base_val = float(base_val_raw)

    classes = list(estimator.classes_)
    pos_idx = classes.index(1) if 1 in classes else -1
    prediction = float(estimator.predict_proba(X_transformed)[0][pos_idx]) if pos_idx >= 0 else 0.5
    raw_values = list(X_transformed[0])

    return feature_names_out, raw_values, shap_row, base_val, prediction


def _shap_regressor(model, row_df: "pd.DataFrame") -> tuple[list, list, list, float, float]:
    """Return (names, values, shap_vals, base_val, prediction) for the regressor."""
    import numpy as np
    import shap
    from config import config

    preprocessor = model.named_steps[config.PREPROCESSING_STEP_NAME]
    estimator = model.named_steps[config.MODEL_STEP_NAME]

    X_transformed = preprocessor.transform(row_df)
    try:
        feature_names_out = list(preprocessor.get_feature_names_out())
    except Exception:
        feature_names_out = [f"f{i}" for i in range(X_transformed.shape[1])]

    explainer = shap.TreeExplainer(estimator)
    shap_vals = explainer.shap_values(X_transformed)
    if isinstance(shap_vals, list):
        sv = shap_vals[0]
    else:
        sv = shap_vals
    shap_row = sv[0].tolist() if hasattr(sv[0], "tolist") else list(sv[0])

    base_val_raw = explainer.expected_value
    if isinstance(base_val_raw, (list, np.ndarray)):
        base_val = float(base_val_raw[0])
    else:
        base_val = float(base_val_raw)

    prediction = float(estimator.predict(X_transformed)[0])
    raw_values = list(X_transformed[0])

    return feature_names_out, raw_values, shap_row, base_val, prediction


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_shap_panel(application: dict, likelihood: dict, duration: dict) -> None:
    """Render the SHAP explanation inside an expander."""
    with st.expander("🔮 Why this prediction? (SHAP explanation)", expanded=False):

        try:
            import shap  # noqa: F401
        except ImportError:
            callout(
                "SHAP is not installed. Run: pip install shap  then restart the dashboard.",
                tone="warning", title="SHAP not available",
            )
            return

        from config import config

        # ------------------------------------------------------------------ Network Work
        st.markdown(
            '<div style="font-size:13.5px;font-weight:700;color:var(--pw-ink,#16201D);'
            'margin-bottom:4px">Network Work Likelihood</div>',
            unsafe_allow_html=True,
        )
        try:
            nw_model = _load_nw_model()
            if nw_model is None:
                callout("Network work model not found. Train the model first.", tone="warning")
            else:
                row_df = _build_feature_row(
                    application,
                    list(config.NETWORK_WORK_NUMERIC_FEATURES),
                    list(config.NETWORK_WORK_CATEGORICAL_FEATURES),
                )
                names, vals, shap_row, base_val, prediction = _shap_classifier(nw_model, row_df)
                _render_feature_rows(names, vals, shap_row, base_val, prediction,
                                    title="Network Work Model — Feature Contributions")
        except Exception as exc:
            callout(f"Could not compute network work SHAP values: {exc}", tone="warning")

        st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)

        # ------------------------------------------------------------------ Duration
        st.markdown(
            '<div style="font-size:13.5px;font-weight:700;color:var(--pw-ink,#16201D);'
            'margin-bottom:4px">Expected Working Days</div>',
            unsafe_allow_html=True,
        )
        try:
            dur_model = _load_dur_model()
            if dur_model is None:
                callout("Duration model not found. Train the model first.", tone="warning")
            else:
                row_df = _build_feature_row(
                    application,
                    list(config.DURATION_NUMERIC_FEATURES),
                    list(config.DURATION_CATEGORICAL_FEATURES),
                )
                names, vals, shap_row, base_val, prediction = _shap_regressor(dur_model, row_df)
                _render_feature_rows(names, vals, shap_row, base_val, prediction,
                                    title="Duration Model — Feature Contributions",
                                    unit=" days")
        except Exception as exc:
            callout(f"Could not compute duration SHAP values: {exc}", tone="warning")

        # ------------------------------------------------------------------ Footer
        st.markdown(
            '<div style="font-size:11.5px;color:var(--pw-muted,#6A7471);margin-top:12px;'
            'padding-top:10px;border-top:1px solid var(--pw-line,#E4E6E1)">'
            'SHAP (SHapley Additive exPlanations) measures each feature\'s contribution to '
            'the prediction relative to the average. Positive values push the prediction higher; '
            'negative values push it lower.</div>',
            unsafe_allow_html=True,
        )

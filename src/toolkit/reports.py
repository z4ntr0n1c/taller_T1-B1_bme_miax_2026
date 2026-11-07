"""Presentation, Markdown reporting, and Matplotlib visualization layer.

Following the separation of concerns used in ``findata.display`` and the layered
architecture (``data -> utils -> models -> reports``), all Markdown formatting
and Matplotlib figure construction live here rather than inside domain classes.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from .monte_carlo import MonteCarloResult
    from .portfolio import Portfolio


def _save_figure(fig: Any, save_path: str | Path | None, show: bool) -> None:
    """Save a Matplotlib figure to disk (creating parent folders) and optionally display it."""
    import matplotlib.pyplot as plt

    if save_path is not None:
        target = Path(save_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(target, dpi=300, bbox_inches="tight")

    if show:
        plt.show()
    else:
        plt.close(fig)



def build_portfolio_report(
    portfolio: Portfolio,
    risk_free_rate: float = 0.0,
    confidence_level: float = 0.95,
    output_path: str | Path | None = None,
) -> str:
    """Generate a structured, publication-ready analytical report in Markdown.

    Args:
        portfolio: The :class:`Portfolio` instance to summarize.
        risk_free_rate: Annualized risk-free benchmark rate (default: 0.0).
        confidence_level: Confidence level for VaR and CVaR (default: 0.95).
        output_path: Optional file path to export the Markdown document.

    Returns:
        Markdown string with formatted tables and automated risk diagnostics.
    """
    conf_pct = int(confidence_level * 100)
    cum_ret = float((1.0 + portfolio.portfolio_returns).prod() - 1.0)
    ann_ret = portfolio.annualized_return()
    ann_vol = portfolio.annualized_volatility()
    sharpe = portfolio.sharpe_ratio(risk_free_rate=risk_free_rate)
    max_dd = portfolio.max_drawdown()
    hist_var = portfolio.value_at_risk(confidence_level, method="historical")
    param_var = portfolio.value_at_risk(confidence_level, method="parametric")
    cvar = portfolio.conditional_value_at_risk(confidence_level)

    def _format_asset_row(asset: Any) -> str:
        return (
            f"| `{asset.ticker}` | {asset.asset_type.capitalize()} | "
            f"{portfolio.weights_dict[asset.ticker]:.1%} | {asset.mean_return:+.4f} | "
            f"{asset.annualized_return():+.2%} | {asset.annualized_volatility():.2%} | "
            f"{asset.sharpe_ratio(risk_free_rate):.2f} | {asset.max_drawdown():.2%} |"
        )

    asset_rows = list(map(_format_asset_row, portfolio.assets))
    asset_table = "\n".join(asset_rows)

    corr_df = portfolio.correlation_matrix.round(3)
    corr_headers = "| | " + " | ".join(map(lambda col: f"`{col}`", corr_df.columns)) + " |"
    corr_sep = "|---|" + "---|" * len(corr_df.columns)
    corr_formatted = corr_df.map(lambda val: f"{val:.3f}")
    corr_rows = list(
        map(
            lambda item: f"| `{item[0]}` | " + " | ".join(item[1]) + " |",
            zip(corr_formatted.index, corr_formatted.to_numpy().tolist(), strict=False),
        )
    )
    corr_table = "\n".join([corr_headers, corr_sep, *corr_rows])

    diagnostics = _build_risk_diagnostics(portfolio, conf_pct, max_dd, hist_var)

    md_content = f"""# 📊 Portfolio Quantitative Analysis & Risk Report: {portfolio.name}

> Generated on: **{portfolio.end_date}** | MIAX-BME Quantitative Analytics Toolkit  
> Base Nominal Capital: **{portfolio.initial_capital:,.2f}** | Observations: **{len(portfolio.portfolio_returns)} trading days** ({portfolio.start_date} to {portfolio.end_date})

---

## 1. Executive Summary

| Metric | Portfolio Value | Description / Interpretation |
|---|---|---|
| **Cumulative Return** | **{cum_ret:+.2%}** | Total compound growth over the observation period |
| **Annualized Return** | **{ann_ret:+.2%}** | Geometric annualized expected compound rate |
| **Annualized Volatility** | **{ann_vol:.2%}** | Annualized standard deviation (σ × √252) |
| **Sharpe Ratio (Rf={risk_free_rate:.1%})** | **{sharpe:.2f}** | Excess return per unit of volatility |
| **Maximum Drawdown** | **{max_dd:.2%}** | Maximum peak-to-trough decline |
| **Historical Daily VaR ({conf_pct}%)** | **{hist_var:.2%}** | Maximum expected daily loss at {conf_pct}% confidence (Empirical) |
| **Parametric Daily VaR ({conf_pct}%)** | **{param_var:.2%}** | Daily {conf_pct}% Value at Risk under Gaussian assumption |
| **Daily CVaR / Expected Shortfall ({conf_pct}%)** | **{cvar:.2%}** | Average loss in the worst {100 - conf_pct}% tail distribution |

---

## 2. Asset Allocation Breakdown

| Ticker | Type | Weight | Daily Mean | Ann. Return | Ann. Vol | Sharpe | Max DD |
|---|---|---|---|---|---|---|---|
{asset_table}

---

## 3. Cross-Asset Correlation Matrix

{corr_table}

---

## 4. Automated Risk Diagnostics & Warning Flags

{diagnostics}

---
*Report automatically generated via `Portfolio.report()` (Toolkit BME-MIAX).*
"""

    if output_path is not None:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(md_content, encoding="utf-8")

    return md_content


def _build_risk_diagnostics(
    portfolio: Portfolio,
    conf_pct: int,
    max_dd: float,
    hist_var: float,
) -> str:
    """Evaluate concentration, collinearity, drawdown, and tail-risk thresholds."""
    warnings: list[str] = []

    max_weight_ticker = max(portfolio.weights_dict, key=portfolio.weights_dict.__getitem__)
    max_w = portfolio.weights_dict[max_weight_ticker]
    if max_w > 0.40:
        warnings.append(
            f"- ⚠️ **Concentration Risk Warning**: Asset `{max_weight_ticker}` represents {max_w:.1%} "
            "of the portfolio (exceeds conservative 40% diversification threshold)."
        )
    else:
        warnings.append(
            "- ✅ **Concentration**: Well-balanced asset allocations (< 40% max per position)."
        )

    corr_vals = portfolio.correlation_matrix.to_numpy(dtype=float)
    idx_i, idx_j = np.where(np.triu(corr_vals, k=1) > 0.75)
    tickers_arr = np.asarray(portfolio.tickers, dtype=str)
    high_corrs = list(
        map(
            lambda t_i, t_j, r: f"`{t_i}` & `{t_j}` (r = {r:.2f})",
            tickers_arr[idx_i],
            tickers_arr[idx_j],
            corr_vals[idx_i, idx_j],
        )
    )
    if high_corrs:
        warnings.append(
            "- ⚠️ **Collinearity / Low Diversification Warning**: Strong positive correlation detected between: "
            + ", ".join(high_corrs)
            + ". This dampens portfolio diversification benefits."
        )
    else:
        warnings.append(
            "- ✅ **Diversification**: No excessive collinearity detected between pairs (all pairwise r ≤ 0.75)."
        )

    if max_dd < -0.20:
        warnings.append(
            f"- ⚠️ **Severe Drawdown Warning**: Historical maximum drawdown of {max_dd:.2%} "
            "exceeds the 20% moderate risk threshold."
        )
    else:
        warnings.append(
            f"- ✅ **Drawdown Profile**: Maximum historical peak-to-trough decline contained at {max_dd:.2%}."
        )

    if abs(hist_var) > 0.025:
        warnings.append(
            f"- ⚠️ **Tail Risk Alert**: Daily {conf_pct}% VaR is {hist_var:.2%}, "
            "indicating significant potential for intraday tail loss."
        )

    return "\n".join(warnings)


def plot_portfolio_dashboard(
    portfolio: Portfolio,
    figsize: tuple[int, int] = (16, 11),
    save_path: str | Path | None = None,
    show: bool = True,
) -> Any:
    """Generate a 2x2 analytics visual dashboard for a :class:`Portfolio`.

    Args:
        portfolio: The :class:`Portfolio` to visualize.
        figsize: Figure size in inches (default: ``(16, 11)``).
        save_path: Optional file path to export the figure.
        show: Whether to invoke ``plt.show()``.

    Returns:
        Tuple of ``(matplotlib.figure.Figure, np.ndarray of Axes)``.
    """
    import matplotlib.pyplot as plt

    fig, axs = plt.subplots(2, 2, figsize=figsize)
    fig.suptitle(
        f"Portfolio Quantitative Diagnostics & Visual Dashboard: {portfolio.name}",
        fontsize=15,
        fontweight="bold",
        y=0.98,
    )

    ax_perf, ax_dd = axs[0, 0], axs[0, 1]
    ax_corr, ax_dist = axs[1, 0], axs[1, 1]
    dates = portfolio.portfolio_returns.index

    # Panel 1: Comparative Cumulative Performance (vectorized across all assets)
    port_cum = (1.0 + portfolio.portfolio_returns).cumprod()
    ax_perf.plot(
        dates, port_cum, color="#1e40af", linewidth=2.5, label=f"Portfolio ({portfolio.name})"
    )

    colors = ["#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4"]
    assets_cum_df = (1.0 + portfolio.returns_df).cumprod()
    list(
        map(
            lambda item: ax_perf.plot(
                dates,
                assets_cum_df[item[1].ticker],
                color=colors[item[0] % len(colors)],
                linewidth=1.2,
                linestyle="--",
                alpha=0.8,
                label=f"{item[1].ticker} ({portfolio.weights_dict[item[1].ticker]:.0%})",
            ),
            enumerate(portfolio.assets),
        )
    )

    ax_perf.axhline(1.0, color="#64748b", linestyle=":", linewidth=1.0)
    ax_perf.set_title(
        "1. Comparative Cumulative Performance (Base 1.0)", fontsize=11, fontweight="bold"
    )
    ax_perf.set_ylabel("Normalized Growth", fontsize=10)
    ax_perf.grid(True, linestyle=":", alpha=0.5)
    ax_perf.legend(loc="upper left", fontsize=8.5, framealpha=0.9)

    # Panel 2: Underwater Drawdown Evolution
    dd = portfolio.drawdown_series()
    ax_dd.plot(dates, dd, color="#dc2626", linewidth=1.5, label="Drawdown")
    ax_dd.fill_between(dates, dd, 0, color="#ef4444", alpha=0.25)
    max_dd_val = float(dd.min())
    max_dd_date = dd.idxmin()
    ax_dd.axhline(
        max_dd_val,
        color="#7f1d1d",
        linestyle="--",
        linewidth=1.4,
        label=f"Max Drawdown: {max_dd_val:.2%}",
    )
    ax_dd.scatter([max_dd_date], [max_dd_val], color="#7f1d1d", zorder=5, s=40)
    ax_dd.set_title(
        "2. Historical Portfolio Underwater Drawdown", fontsize=11, fontweight="bold"
    )
    ax_dd.set_ylabel("Drawdown (%)", fontsize=10)
    ax_dd.grid(True, linestyle=":", alpha=0.5)
    ax_dd.legend(loc="lower left", fontsize=8.5, framealpha=0.9)

    # Panel 3: Correlation Matrix Heatmap
    corr = portfolio.correlation_matrix.to_numpy(dtype=float)
    tickers = portfolio.tickers
    im = ax_corr.imshow(corr, cmap="coolwarm", vmin=-1.0, vmax=1.0)
    plt.colorbar(im, ax=ax_corr, fraction=0.046, pad=0.04)

    ax_corr.set_xticks(range(len(tickers)))
    ax_corr.set_yticks(range(len(tickers)))
    ax_corr.set_xticklabels(tickers, rotation=45, ha="right", fontsize=9)
    ax_corr.set_yticklabels(tickers, fontsize=9)

    grid_i, grid_j = np.indices(corr.shape)
    flat_vals = corr.ravel()
    text_colors = np.where(np.abs(flat_vals) > 0.55, "white", "black")
    list(
        map(
            lambda i, j, val, col: ax_corr.text(
                int(j),
                int(i),
                f"{float(val):.2f}",
                ha="center",
                va="center",
                color=str(col),
                fontsize=9,
                fontweight="bold",
            ),
            grid_i.ravel(),
            grid_j.ravel(),
            flat_vals,
            text_colors,
        )
    )

    ax_corr.set_title("3. Asset Correlation Heatmap", fontsize=11, fontweight="bold")

    # Panel 4: Daily Return Distribution & Risk Cutoffs
    n_bins = min(50, max(20, len(portfolio.portfolio_returns) // 8))
    _, bins, _ = ax_dist.hist(
        portfolio.portfolio_returns,
        bins=n_bins,
        density=True,
        color="#93c5fd",
        edgecolor="#2563eb",
        alpha=0.6,
        label="Daily Returns",
    )

    var_95 = portfolio.value_at_risk(0.95, method="historical")
    cvar_95 = portfolio.conditional_value_at_risk(0.95)
    mean_ret = portfolio.mean_return

    ax_dist.axvline(
        mean_ret, color="#1e40af", linestyle="-", linewidth=1.8, label=f"Mean: {mean_ret:+.2%}"
    )
    ax_dist.axvline(
        var_95, color="#f97316", linestyle="--", linewidth=1.8, label=f"95% VaR: {var_95:.2%}"
    )
    ax_dist.axvline(
        cvar_95, color="#dc2626", linestyle="--", linewidth=1.8, label=f"95% CVaR: {cvar_95:.2%}"
    )

    if len(bins[bins <= var_95]) > 1:
        ax_dist.axvspan(
            bins[0], var_95, color="#ef4444", alpha=0.18, label="5% Tail Loss Zone"
        )

    ax_dist.set_title(
        "4. Daily Return Distribution & Tail Risk Cutoffs", fontsize=11, fontweight="bold"
    )
    ax_dist.set_xlabel("Daily Return", fontsize=10)
    ax_dist.set_ylabel("Probability Density", fontsize=10)
    ax_dist.grid(True, linestyle=":", alpha=0.5)
    ax_dist.legend(loc="upper right", fontsize=8.5, framealpha=0.9)

    plt.tight_layout()
    _save_figure(fig, save_path, show)
    return fig, axs


def plot_monte_carlo(
    result: MonteCarloResult,
    title: str | None = None,
    max_paths_to_display: int = 150,
    confidence_level: float = 0.95,
    figsize: tuple[int, int] = (14, 6),
    save_path: str | Path | None = None,
    show: bool = True,
) -> Any:
    """Visualize Monte Carlo simulated trajectories and terminal value distribution.

    Args:
        result: The :class:`MonteCarloResult` to plot.
        title: Custom super-title for the figure.
        max_paths_to_display: Number of sample paths to plot.
        confidence_level: Confidence level for VaR line and intervals.
        figsize: Figure dimensions in inches.
        save_path: Optional path to export the figure.
        show: Whether to invoke ``plt.show()``.

    Returns:
        Tuple of ``(matplotlib.figure.Figure, (ax1, ax2))``.
    """
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
    plot_title = title or (
        f"Monte Carlo Simulation: {result.name} "
        f"({result.n_simulations:,} paths, T={result.horizon}d)"
    )
    fig.suptitle(plot_title, fontsize=14, fontweight="bold", y=0.98)

    # Subplot 1: Trajectories
    display_n = min(result.n_simulations, max_paths_to_display)
    ax1.plot(
        result.time_steps,
        result.trajectories[:, :display_n],
        color="#2563eb",
        alpha=0.10,
        linewidth=0.8,
    )

    q_levels = np.array([(1.0 - confidence_level) * 100.0, 50.0, confidence_level * 100.0])
    p_lower, median_path, p_upper = np.percentile(result.trajectories, q_levels, axis=1)

    ax1.plot(result.time_steps, median_path, color="#ea580c", linewidth=2.2, label="Median Path")
    ax1.plot(
        result.time_steps,
        p_upper,
        color="#16a34a",
        linestyle="--",
        linewidth=1.8,
        label=f"{int(confidence_level * 100)}th Percentile",
    )
    ax1.plot(
        result.time_steps,
        p_lower,
        color="#dc2626",
        linestyle="--",
        linewidth=1.8,
        label=f"{int((1.0 - confidence_level) * 100)}th Percentile",
    )
    ax1.axhline(
        result.initial_value,
        color="#475569",
        linestyle=":",
        linewidth=1.5,
        label=f"Initial ({result.initial_value:,.1f})",
    )
    ax1.fill_between(result.time_steps, p_lower, p_upper, color="#2563eb", alpha=0.08)

    ax1.set_title(
        "Simulated Trajectories (Sample Paths & Envelopes)", fontsize=11, fontweight="bold"
    )
    ax1.set_xlabel("Time Horizon (Trading Days)", fontsize=10)
    ax1.set_ylabel("Value", fontsize=10)
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.legend(loc="upper left", fontsize=9, framealpha=0.9)

    # Subplot 2: Terminal Distribution
    n_bins = min(60, max(20, result.n_simulations // 40))
    _, bins, _ = ax2.hist(
        result.terminal_values,
        bins=n_bins,
        density=True,
        color="#93c5fd",
        edgecolor="#1d4ed8",
        alpha=0.65,
        label="Terminal Distribution",
    )

    var_threshold = float(
        np.percentile(result.terminal_values, (1.0 - confidence_level) * 100.0)
    )

    ax2.axvline(
        result.initial_value,
        color="#475569",
        linestyle=":",
        linewidth=1.5,
        label=f"Initial: {result.initial_value:,.1f}",
    )
    ax2.axvline(
        result.terminal_mean,
        color="#ea580c",
        linestyle="-",
        linewidth=2.0,
        label=f"Mean: {result.terminal_mean:,.1f}",
    )
    ax2.axvline(
        var_threshold,
        color="#dc2626",
        linestyle="--",
        linewidth=1.8,
        label=f"{int(confidence_level * 100)}% VaR Cutoff: {var_threshold:,.1f}",
    )

    if len(bins[bins <= var_threshold]) > 1:
        ax2.axvspan(
            bins[0],
            var_threshold,
            color="#ef4444",
            alpha=0.15,
            label=f"Tail Loss (P={1 - confidence_level:.0%})",
        )

    ax2.set_title(
        f"Terminal Value Distribution (at T={result.horizon})", fontsize=11, fontweight="bold"
    )
    ax2.set_xlabel("Terminal Value", fontsize=10)
    ax2.set_ylabel("Probability Density", fontsize=10)
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend(loc="upper right", fontsize=9, framealpha=0.9)

    plt.tight_layout()
    _save_figure(fig, save_path, show)
    return fig, (ax1, ax2)

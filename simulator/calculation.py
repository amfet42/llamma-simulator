import json
import logging

from numpy import log10, logspace

from simulator.amm.intitial_liquidity import ConstantInitialLiquidity
from simulator.amm.price_history_loader import GenericPriceHistoryLoader
from simulator.amm.price_oracle import EmaPriceOracle
from simulator.amm.simulator import Simulator
from simulator.settings import BASE_DIR, Pair

logger = logging.getLogger(__name__)


class Calculator:
    EXTERNAL_FEE = 5e-4  # fee paid by arbitragers to external platforms

    @classmethod
    def simulate_A(
        cls,
        pair: str,
        t_exp: int,
        samples: int = 500000,
        n_top_samples: int = 50,
        dynamic_fee_multiplier: float | None = 0.25,
        min_loan_duration: float | None = None,
        max_loan_duration: float | None = None,
        initial_liquidity_range: int = 4,
    ):
        price_oracle = EmaPriceOracle(t_exp=t_exp)
        price_history_loader = GenericPriceHistoryLoader(pair=Pair(pair))

        simulator = Simulator(
            initial_liquidity_class=ConstantInitialLiquidity,
            price_history_loader=price_history_loader,
            price_oracle=price_oracle,
            external_fee=cls.EXTERNAL_FEE,
        )

        losses = []
        discounts = []

        kwargs = {
            "samples": samples,
            "n_top_samples": n_top_samples,
            "initial_liquidity_range": initial_liquidity_range,
            "dynamic_fee_multiplier": dynamic_fee_multiplier,
            "min_loan_duration": min_loan_duration,
            "max_loan_duration": max_loan_duration,
        }

        a_range = [int(a) for a in logspace(log10(30), log10(500), 30)]
        for a in a_range:
            kwargs_with_a = {**kwargs, "A": a}
            loss = simulator.get_loss_rate(**kwargs_with_a)

            # Simplified formula
            # bands_coefficient = (((A - 1) / A) ** range_size) ** 0.5
            # More precise
            bands_coefficient = (
                sum(((a - 1) / a) ** (k + 0.5) for k in range(initial_liquidity_range)) / initial_liquidity_range
            )
            liquidation_discount = 1 - (1 - loss) * bands_coefficient

            logger.info(f"Params: {kwargs_with_a}, loss: {loss}, liquidation discount: {liquidation_discount}")

            losses.append(loss)
            discounts.append(liquidation_discount)

        results = [(a_range, losses), (a_range, discounts)]

        save_json_results(pair, f"losses_A__{samples}_{n_top_samples}", results)
        save_plot(
            pair,
            f"losses_A__{samples}_{n_top_samples}",
            (a_range, losses),
            (a_range, discounts),
            {"xlabel": "A", "ylabel": "Loss"},
            kwargs,
        )
        return results

    @classmethod
    def simulate_range(
        cls,
        pair: str,
        t_exp: int,
        a: int,
        samples: int = 500000,
        n_top_samples: int = 50,
        dynamic_fee_multiplier: float | None = 0.25,
        min_loan_duration: float | None = None,
        max_loan_duration: float | None = None,
    ):
        price_oracle = EmaPriceOracle(t_exp=t_exp)
        price_history_loader = GenericPriceHistoryLoader(pair=Pair(pair))

        simulator = Simulator(
            initial_liquidity_class=ConstantInitialLiquidity,
            price_history_loader=price_history_loader,
            price_oracle=price_oracle,
            external_fee=cls.EXTERNAL_FEE,
        )

        losses = []
        discounts = []

        kwargs = {
            "samples": samples,
            "n_top_samples": n_top_samples,
            "A": a,
            "dynamic_fee_multiplier": dynamic_fee_multiplier,
            "min_loan_duration": min_loan_duration,
            "max_loan_duration": max_loan_duration,
        }

        liquidity_range = list(range(4, 50, 4))
        for initial_liquidity_range in liquidity_range:
            kwargs_with_a = {**kwargs, "initial_liquidity_range": initial_liquidity_range}
            loss = simulator.get_loss_rate(**kwargs_with_a)

            # Simplified formula
            # bands_coefficient = (((A - 1) / A) ** range_size) ** 0.5
            # More precise
            bands_coefficient = (
                sum(((a - 1) / a) ** (k + 0.5) for k in range(initial_liquidity_range)) / initial_liquidity_range
            )
            liquidation_discount = 1 - (1 - loss) * bands_coefficient

            logger.info(f"Params: {kwargs_with_a}, loss: {loss}, liquidation discount: {liquidation_discount}")

            losses.append(loss)
            discounts.append(liquidation_discount)

        results = [(liquidity_range, losses), (liquidity_range, discounts)]

        save_json_results(pair, f"losses_initial_range__{samples}_{n_top_samples}", results)
        save_plot(
            pair,
            f"losses_range__{samples}_{n_top_samples}",
            (liquidity_range, losses),
            (liquidity_range, discounts),
            {"xlabel": "Initial range N", "ylabel": "Loss"},
            kwargs,
        )
        return results

    @classmethod
    def simulate_dynamic_fee(
        cls,
        pair: str,
        t_exp: int,
        a: int,
        samples: int = 500000,
        n_top_samples: int = 50,
        min_loan_duration: float | None = None,
        max_loan_duration: float | None = None,
        initial_liquidity_range: int = 4,
    ):
        price_oracle = EmaPriceOracle(t_exp=t_exp)
        price_history_loader = GenericPriceHistoryLoader(pair=Pair(pair))

        simulator = Simulator(
            initial_liquidity_class=ConstantInitialLiquidity,
            price_history_loader=price_history_loader,
            price_oracle=price_oracle,
            external_fee=cls.EXTERNAL_FEE,
        )

        losses = []
        discounts = []

        kwargs = {
            "samples": samples,
            "n_top_samples": n_top_samples,
            "A": a,
            "initial_liquidity_range": initial_liquidity_range,
            "min_loan_duration": min_loan_duration,
            "max_loan_duration": max_loan_duration,
        }

        d_fee_range = [d / 100 for d in range(10, 50, 3)]
        for d_fee in d_fee_range:
            kwargs_with_a = {**kwargs, "dynamic_fee_multiplier": d_fee}
            loss = simulator.get_loss_rate(**kwargs_with_a)

            # Simplified formula
            # bands_coefficient = (((A - 1) / A) ** range_size) ** 0.5
            # More precise
            bands_coefficient = (
                sum(((a - 1) / a) ** (k + 0.5) for k in range(initial_liquidity_range)) / initial_liquidity_range
            )
            liquidation_discount = 1 - (1 - loss) * bands_coefficient

            logger.info(f"Params: {kwargs_with_a}, loss: {loss}, liquidation discount: {liquidation_discount}")

            losses.append(loss)
            discounts.append(liquidation_discount)

        results = [(d_fee_range, losses), (d_fee_range, discounts)]

        save_json_results(pair, f"losses_dynamic_fee__{samples}_{n_top_samples}", results)
        save_plot(
            pair,
            f"losses_dynamic_fee__{samples}_{n_top_samples}",
            (d_fee_range, losses),
            (d_fee_range, discounts),
            {"xlabel": "Dynamic fee", "ylabel": "Loss"},
            kwargs,
        )
        return results


def save_plot(
    pair: str,
    file_name: str,
    losses: tuple,
    discounts: tuple,
    plot_kwargs: dict,
    capture_kwargs: dict,
):
    import matplotlib.pyplot as plt

    plt.plot(losses[0], losses[1], label="Loss")
    plt.plot(discounts[0], discounts[1], label="Liquidation Discount")

    # Min liquidation discount
    min_discount = min(discounts[1])
    min_discount_index = discounts[1].index(min_discount)
    min_discount_A = discounts[0][min_discount_index]
    plt.axvline(x=min_discount_A, color="black", linestyle="--", linewidth=2)
    plt.text(
        min_discount_A * 1.05,
        max(discounts[1]) * 0.4,
        f"{plot_kwargs.get('xlabel', 'x')} = {min_discount_A}, Discount={min_discount:.3f}",
        rotation=90,
        color="black",
        va="bottom",
    )

    # Caption text for parameters
    plt.text(
        max(discounts[0]) * 15 / 100,
        max(discounts[1]),  # (x, y) position on chart
        "\n".join(f"{k}: {capture_kwargs[k]}" for k in capture_kwargs if capture_kwargs[k] is not None),
        color="black",
        bbox=dict(
            facecolor="lightyellow",  # background color
            edgecolor="black",  # border color
            boxstyle="round,pad=0.5",  # rounded corners and padding
        ),
    )

    plt.grid()
    plt.xlabel(plot_kwargs.get("xlabel", "x"))
    plt.ylabel(plot_kwargs.get("ylabel", "Loss"))
    plt.legend(loc="best")

    path = BASE_DIR / "results" / pair / f"{file_name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=300, bbox_inches="tight")


def save_json_results(pair, file_name, results):
    path = BASE_DIR / "results" / pair / f"{file_name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(results, f)

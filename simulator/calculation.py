from collections.abc import Iterable

from simulator.amm.intitial_liquidity import ConstantInitialLiquidity
from simulator.amm.price_history_loader import GenericPriceHistoryLoader
from simulator.amm.price_oracle import EmaPriceOracle
from simulator.amm.simulator import Simulator
from simulator.settings import BASE_DIR, Pair

EXT_FEE = 5e-4


def scan_param(pair: str, t_exp, **kw):
    price_oracle = EmaPriceOracle(t_exp=t_exp)
    price_history_loader = GenericPriceHistoryLoader(pair=Pair(pair))
    simulator = Simulator(
        initial_liquidity_class=ConstantInitialLiquidity,
        price_oracle=price_oracle,
        external_fee=EXT_FEE,
        price_history_loader=price_history_loader,
    )
    args = {"samples": 50, "n_top_samples": 5, "min_loan_duration": 0.15, "max_loan_duration": 0.15}
    args.update(kw)
    iterable_args = [k for k in kw if isinstance(kw[k], Iterable) and not isinstance(kw[k], dict)]
    assert len(iterable_args) == 1, "Not one iterable item"
    scanned_name = iterable_args[0]
    scanned_args = kw[scanned_name]
    del args[scanned_name]

    losses = []
    discounts = []

    for v in scanned_args:
        args[scanned_name] = v
        loss = simulator.get_loss_rate(**args)
        A = args["A"]
        initial_liquidity_range = args["initial_liquidity_range"]

        # Simplified formula
        # bands_coefficient = (((A - 1) / A) ** range_size) ** 0.5
        # More precise
        bands_coefficient = (
            sum(((A - 1) / A) ** (k + 0.5) for k in range(initial_liquidity_range)) / initial_liquidity_range
        )
        cl = 1 - (1 - loss) * bands_coefficient

        print(f"{scanned_name}={v}\t->\tLoss={loss},\tLiq_discount={cl}")

        losses.append(loss)
        discounts.append(cl)

    save_plot(pair, "losses", f"losses__{'_'.join(str(k) for k in args.values())}]", (scanned_args, losses))
    save_plot(pair, "discounts", f"discounts__{'_'.join(str(k) for k in args.values())}]", (scanned_args, discounts))
    return [(scanned_args, losses), (scanned_args, discounts)]


def save_plot(pair: str, parameter_name: str, file_name: str, losses: tuple):
    import matplotlib.pyplot as plt

    x, y = losses

    plt.plot(x, y)
    plt.grid()
    plt.ylabel("Loss")
    plt.xlabel(parameter_name)

    path = BASE_DIR / "results" / pair / f"{file_name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=300, bbox_inches="tight")

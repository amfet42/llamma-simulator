import logging
import sys

import click
from numpy import log10, logspace

from simulator.calculation import scan_param
from simulator.import_data import BinanceImporter
from simulator.settings import Pair

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.handlers = []

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


@click.group("simulator")
def simulator_commands(): ...


@simulator_commands.command("import_data", short_help="import price data")
@click.argument("pair", type=click.STRING)
def import_data(pair: str) -> None:
    BinanceImporter.run(Pair(pair))


# Change parameters before running
@simulator_commands.command("calculate", short_help="import price data")
def calculate() -> None:
    """
    One of the parameters is iterable (i.e. fee)

    pair - name of pair - "BTCUSDT"
    A - AMM parameter A
    initial_liquidity_range - number of bands initially to have liquidity
    fee - protocol fee
    t_exp - exponential time for oracle EMA
    samples - number of samples to iterate through
    n_top_samples - number of top samples to choose (worst case)
    min_loan_duration - from 0 to 1 duration of loan (1 is whole price data range)
    max_loan_duration - from 0 to 1 duration of loan (1 is whole price data range)
    loan range is chosen randomly from min_loan_duration to max_loan_duration
    """
    results = scan_param(
        pair="BTCUSDT",
        A=100,
        initial_liquidity_range=4,
        fee=logspace(log10(0.0005), log10(0.03), 20),
        t_exp=600,
        samples=500000,
        n_top_samples=50000,
        min_loan_duration=1 / 24,
        max_loan_duration=1 / 24,
    )
    print(results)


if __name__ == "__main__":
    simulator_commands()

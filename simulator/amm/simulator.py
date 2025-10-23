import logging
import random
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

from .intitial_liquidity import BaseRangeInitialLiquidity
from .lending_amm import LendingAMM
from .price_history_loader import BasePriceHistoryLoader
from .price_oracle import BasePriceOracle

logger = logging.getLogger(__name__)


class Simulator:

    def __init__(
        self,
        initial_liquidity_class: type[BaseRangeInitialLiquidity],
        price_history_loader: BasePriceHistoryLoader,
        price_oracle: BasePriceOracle,
        external_fee: float = 0.0,  # should be 0 < external_fee < 1
    ):
        """
        :param initial_liquidity_class: initial liquidity for AMM (class, initialized in simulator), min=4 worst case
        :param price_history_loader: load prices source
        :param price_oracle: oracle prices calculater (can choose different oracles)
        :param external_fee: fee paid by arbitragers to external platforms

        min_loan_duration: minimal duration of loan in liquidation in days (actual is chosen randomly every run)
        max_loan_duration: maximum duration of loan in liquidation days (actual is chosen randomly every run)
        log_enabled: enable logging
        verbose: Output losses after each iteration for every run

        Usually positions are in liquidation in < 30 min so 1/48 is reasonable approximation
        """

        self.initial_liquidity_class = initial_liquidity_class
        self.price_history_loader = price_history_loader
        self.price_oracle = price_oracle
        self.external_fee = external_fee

        # Default parameters
        self.samples = 400
        self.min_loan_duration = 1 / 48  # days
        self.max_loan_duration = 1 / 24  # days
        self.log_enabled: bool = False
        self.verbose: bool = False

        self.prices = self.load_prices()
        self.oracle_prices = self.calculate_oracle_price(self.prices)

    def load_prices(self) -> list:
        return self.price_history_loader.load_prices()

    def calculate_oracle_price(self, prices: list) -> list:
        return self.price_oracle.calculate_oracle_prices(prices)

    def single_run(
        self,
        A: int,
        position_start: float,  # [0, 1)
        position_period: float,  # [0, 1 - position_start)
        initial_liquidity_range: int,  # p0 then n number of bands
        dynamic_fee_multiplier: float | None = None,
        position_shift: float = 0,  # [0, 1) how much lower from current prices
    ):
        """
        position: 0..1
        size: fraction of all price data length for size
        """
        # Data for prices
        position_start_index = int(position_start * len(self.prices))  # start of position in prices array
        position_end_index = int(
            (position_start + position_period) * len(self.prices)
        )  # end of position in prices array

        prices_for_simulation = self.prices[position_start_index:position_end_index]
        oracle_prices_for_simulation = self.oracle_prices[position_start_index:position_end_index]
        p0 = prices_for_simulation[0][1] * (1 - position_shift)

        initial_y0 = 1.0  # 1 ETH
        p_base = p0 * (A / (A - 1) + 1e-4)
        initial_x_value = initial_y0 * p_base
        amm = LendingAMM(p_base, A, dynamic_fee_multiplier)

        # Fill ticks with liquidity
        self.initial_liquidity_class(p0, initial_liquidity_range).deposit(amm, initial_y0)
        initial_all_x = amm.get_all_x()

        xs_normalized = []
        fees = []

        def find_target_price(p, is_up=True):
            # Find target band
            if is_up:
                for n in range(amm.max_band, amm.min_band - 1, -1):
                    p_down = amm.p_down(n)
                    d_fee = amm.dynamic_fee(n)
                    p_down_with_fee = p_down * (1 + d_fee)

                    if p > p_down_with_fee:
                        return p * (1 - d_fee)

            else:
                for n in range(amm.min_band, amm.max_band + 1):
                    p_up = amm.p_up(n)
                    d_fee = amm.dynamic_fee(n)
                    p_up_ = p_up * (1 - d_fee)

                    if p < p_up_:
                        return p * (1 + d_fee)

            # price is outside of liquidity
            if is_up:
                return p * (1 - amm.dynamic_fee(amm.min_band))
            else:
                return p * (1 + amm.dynamic_fee(amm.max_band))

        # <----------------- Calculation ----------------->
        for (t, open, high, low, close, vol), oracle_price in zip(prices_for_simulation, oracle_prices_for_simulation):
            amm.set_p_oracle(oracle_price)

            high = find_target_price(high * (1 - self.external_fee), is_up=True)
            low = find_target_price(low * (1 + self.external_fee), is_up=False)

            if high > amm.get_p():
                amm.trade_to_price(high)

            # Not correct for dynamic fees which are too high
            # if high > max_price:
            #     # Check that AMM has only stablecoins
            #     for n in range(amm.min_band, amm.max_band + 1):
            #         assert amm.bands_y[n] == 0
            #         assert amm.bands_x[n] > 0

            if low < amm.get_p():
                amm.trade_to_price(low)

            # Not correct for dynamic fees which are too high
            # if low < min_price:
            #     # Check that AMM has only collateral
            #     for n in range(amm.min_band, amm.max_band + 1):
            #         assert amm.bands_x[n] == 0
            #         assert amm.bands_y[n] > 0

            d = datetime.fromtimestamp(t).strftime("%Y/%m/%d %H:%M")
            fees.append(amm.dynamic_fee(amm.active_band))
            if self.log_enabled:
                current_x_total_normalized = amm.get_all_x() / initial_x_value
                logger.info(
                    f"Current x total for {d}: {current_x_total_normalized:.4f}, oracle price: {oracle_price:.2f}, amm_price: {amm.get_p():.2f}"
                )

            if self.verbose:
                current_x_total_normalized = amm.get_all_x() / initial_x_value
                xs_normalized.append([t, current_x_total_normalized])

        if self.verbose:
            logger.info(f"Xs after trades list: {xs_normalized}")

        loss = 1 - amm.get_all_x() / initial_all_x
        return loss

    def single_run_kw(self, kw):
        return self.single_run(**kw)

    def get_loss_rate(
        self,
        A: int,
        initial_liquidity_range: int,
        dynamic_fee_multiplier: float | None = None,
        samples: int | None = None,
        n_top_samples: int | None = None,
        max_loan_duration: float | None = None,
        min_loan_duration: float | None = None,
        position_shift: float = 0,
        use_threading: bool = False,  # somehow it's slower
    ):
        if not samples:
            samples = self.samples
        if not max_loan_duration:
            max_loan_duration = self.max_loan_duration
        if not min_loan_duration:
            min_loan_duration = self.min_loan_duration

        day_fraction = 86400 / (self.prices[-1][0] - self.prices[0][0])  # Which fraction of all data is 1 day

        kwargs_list = []
        for _ in range(samples):
            position_start = random.random()
            position_period = min_loan_duration * day_fraction
            position_period += (max_loan_duration - min_loan_duration) * day_fraction * random.random()

            kwargs_list.append(
                {
                    "A": A,
                    "position_start": position_start,
                    "position_period": position_period,
                    "initial_liquidity_range": initial_liquidity_range,
                    "dynamic_fee_multiplier": dynamic_fee_multiplier,
                    "position_shift": position_shift,
                }
            )

        if use_threading:
            with ProcessPoolExecutor(max_workers=8) as pool:
                results = pool.map(self.single_run_kw, kwargs_list)
        else:
            results = []
            for kw in kwargs_list:
                try:
                    sr_result = self.single_run(**kw)
                    if self.log_enabled:
                        logger.info(
                            f"Results A:{kw['A']}, position_start:{kw['position_start']}, "
                            f"position_period:{kw['position_period']}: {kw['sr_result']}"
                        )
                    results.append(sr_result)
                except Exception as e:
                    logger.warning(e)
                    results.append(0)

        if not n_top_samples:
            n_top_samples = samples // 20
        return sum(sorted(results)[::-1][:n_top_samples]) / n_top_samples

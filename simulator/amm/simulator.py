import random
from datetime import datetime

from .intitial_liquidity import BaseRangeInitialLiquidity
from .lending_amm import LendingAMM
from .price_history_loader import BasePriceHistoryLoader
from .price_oracle import BasePriceOracle


class Simulator:

    def __init__(
        self,
        initial_liquidity_class: type[BaseRangeInitialLiquidity],
        price_history_loader: BasePriceHistoryLoader,
        price_oracle: BasePriceOracle,
        external_fee: float,
        min_loan_duration: int = 1,  # days
        max_loan_duration: int = 1,  # days
        samples: int = 400,
        dynamic_fee_multiplier: int = 0,
        use_po_fee: bool = True,
        po_fee_delay: int = 2,
        log_enabled: bool = False,
        verbose: bool = False,
    ):
        """
        :param initial_liquidity:
        :param price_history_loader:
        :param price_oracle:
        :param external_fee: Fee which arb trader pays to external platforms
        :param min_loan_duration:
        :param max_loan_duration:
        :param samples:
        :param dynamic_fee_multiplier:
        :param use_po_fee:
        :param po_fee_delay:
        :param log_enabled:
        :param verbose:
        """

        self.initial_liquidity_class = initial_liquidity_class
        self.price_history_loader = price_history_loader
        self.price_oracle = price_oracle
        self.external_fee = external_fee
        self.min_loan_duration = min_loan_duration
        self.max_loan_duration = max_loan_duration
        self.samples = samples
        self.dynamic_fee_multiplier = dynamic_fee_multiplier
        self.use_po_fee = use_po_fee
        self.po_fee_delay = po_fee_delay
        self.log_enabled = log_enabled
        self.verbose = verbose

        self.oracle_prices = []

    def load_prices(self) -> list:
        return self.price_history_loader.load_prices()

    def calculate_oracle_price(self, prices: list) -> list:
        return self.price_oracle.calculate_oracle_prices(prices)

    def single_run(
        self,
        prices: list,
        A: int,
        fee: float,
        position_start: float,  # [0, 1)
        position_period: float,  # [0, 1 - position_start)
        initial_liquidity_range: int,
        position_shift: float = 0,  # [0, 1)
        **kw,
    ):
        """
        position: 0..1
        size: fraction of all price data length for size
        """
        oracle_prices = self.calculate_oracle_price(prices)

        # Data for prices
        pos = (int(position_start * len(prices)), int((position_start + position_period) * len(prices)))
        data = prices[pos[0] : pos[1]]
        oracle_data = oracle_prices[pos[0] : pos[1]]
        p0 = data[0][1] * (1 - position_shift)

        initial_y0 = 1.0  # 1 ETH
        p_base = p0 * (A / (A - 1) + 1e-4)
        initial_x_value = initial_y0 * p_base
        amm = LendingAMM(p_base, A, fee, **kw)

        # Fill ticks with liquidity
        self.initial_liquidity_class(p0, initial_liquidity_range).deposit(amm, initial_y0)
        initial_all_x = amm.get_all_x()

        losses = []
        fees = []

        def find_target_price(p, is_up=True, new=False):
            if is_up:
                for n in range(amm.max_band, amm.min_band - 1, -1):
                    p_down = amm.p_down(n)
                    dfee = amm.dynamic_fee(n, new=new)
                    p_down_ = p_down * (1 + dfee)
                    # XXX print(n, amm.min_band, amm.max_band, p_down, p, amm.get_p())
                    if p > p_down_:
                        p_up = amm.p_up(n)
                        p_up_ = p_up * (1 + dfee)
                        # if p >= p_up_:
                        #     return p_up
                        # else:
                        return (p - p_down_) / (p_up_ - p_down_) * (p_up - p_down) + p_down
            else:
                for n in range(amm.min_band, amm.max_band + 1):
                    p_up = amm.p_up(n)
                    dfee = amm.dynamic_fee(n, new=new)
                    p_up_ = p_up * (1 - dfee)
                    if p < p_up_:
                        p_down = amm.p_down(n)
                        p_down_ = p_down * (1 - dfee)
                        return p_up - (p_up_ - p) / (p_up_ - p_down_) * (p_up - p_down)

            if is_up:
                return p * (1 - amm.dynamic_fee(amm.min_band, new=False))
            else:
                return p * (1 + amm.dynamic_fee(amm.max_band, new=False))

        for (t, o, high, low, c, vol), oracle_price in zip(data, oracle_data):
            amm.set_p_oracle(oracle_price)
            # max_price = amm.p_up(amm.max_band)
            # min_price = amm.p_down(amm.min_band)
            high = find_target_price(high * (1 - self.external_fee), is_up=True, new=True)
            low = find_target_price(low * (1 + self.external_fee), is_up=False, new=False)
            # high = high * (1 - EXT_FEE - fee)
            # low = low * (1 + EXT_FEE + fee)
            # if high > amm.get_p():
            #     print(high, '/', high_, '/', max_price, '; ', low, '/', low_, '/', min_price)
            if high > amm.get_p():
                try:
                    amm.trade_to_price(high)
                except Exception:
                    print(high, low, amm.get_p())
                    raise

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

            d = datetime.fromtimestamp(t // 1000).strftime("%Y/%m/%d %H:%M")
            fees.append(amm.dynamic_fee(amm.active_band, new=False))
            if self.log_enabled or self.verbose:
                loss = amm.get_all_x() / initial_x_value * 100
                if self.log_enabled:
                    print(f"{d}\t{o:.2f}\t{oracle_price:.2f}\t{amm.get_p():.2f}\t\t{loss:.2f}%")
                if self.verbose:
                    losses.append([t // 1000, loss / 100])

        if losses:
            self.losses = losses

        loss = 1 - amm.get_all_x() / initial_all_x
        return loss

    def get_loss_rate(
        self,
        A: int,
        fee: float,
        initial_liquidity_range: int,
        samples: int | None = None,
        max_loan_duration: float | None = None,
        min_loan_duration: float | None = None,
        n_top_samples: int | None = None,
        other={},
    ):
        _other = {k: v for k, v in other.items()}
        _other.update(other)
        other = _other
        if not samples:
            samples = self.samples

        if not max_loan_duration:
            max_loan_duration = self.max_loan_duration

        if not min_loan_duration:
            min_loan_duration = self.min_loan_duration

        prices = self.load_prices()

        dt = 86400 * 1000 / (prices[-1][0] - prices[0][0])  # Which fraction of all data is 1 day

        result = []
        for _ in range(samples):
            try:
                sr_result = self.single_run(
                    prices=prices,
                    A=A,
                    fee=fee,
                    position_start=random.random(),
                    position_period=(max_loan_duration - min_loan_duration) * dt * random.random()
                    + min_loan_duration * dt,
                    initial_liquidity_range=initial_liquidity_range,
                    position_shift=0,
                    **other,
                )
                print(sr_result)
                result.append(sr_result)
            except Exception as e:
                print(e)
                return 0

        if not n_top_samples:
            n_top_samples = samples // 20
        return sum(sorted(result)[::-1][:n_top_samples]) / n_top_samples

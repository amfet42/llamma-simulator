from abc import ABC, abstractmethod
from enum import StrEnum

from simulator.import_data.binance import BinanceImporter
from simulator.settings import Pair


class ImporterType(StrEnum):
    binance = "binance"


class BasePriceHistoryLoader(ABC):
    @abstractmethod
    def load_prices(self) -> list: ...


class GenericPriceHistoryLoader(BasePriceHistoryLoader):
    def __init__(self, pair: Pair, importer_type: ImporterType = ImporterType.binance, add_reverse: bool = True):
        if importer_type == ImporterType.binance:
            self.importer = BinanceImporter()
        else:
            raise NotImplementedError("Unsupported importer type")

        self.pair = pair
        self.add_reverse = add_reverse

    def load_prices(self) -> list:
        data = self.importer.load(self.pair)

        # timestamp, OHLC, vol
        unfiltered_data = [[int(d[0])] + [float(x) for x in d[1:6]] for d in data]
        data = []
        prev_time = 0
        for d in unfiltered_data:
            if d[0] >= prev_time:
                data.append(d)
                prev_time = d[0]
        if self.add_reverse:
            t0 = data[-1][0]
            data += [[t0 + (t0 - d[0])] + d[1:] for d in data[::-1]]

        return data

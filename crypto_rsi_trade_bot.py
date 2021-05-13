"""
Crypto Bot running based on a given strategy
"""
import logging
from argparse import ArgumentParser

import mplfinance as mpf
from mplfinance.plotting import make_addplot

from common.analyst import resample_candles
from common.logger import init_logging
from common.steps import (
    SetupDatabase,
    FetchAccountInfoFromExchange,
    ReadConfiguration,
    FetchDataFromExchange,
    LoadDataInDataFrame,
    TradeSignal,
    LoadLastTransactionFromDatabase,
    CheckIfIsANewSignal,
    CalculateBuySellAmountBasedOnAllocatedPot,
    ExecuteBuyTradeIfSignaled,
    ExecuteSellTradeIfSignaled,
    RecordTransactionInDatabase,
    PublishTransactionOnTelegram,
    CollectInformationAboutOrder,
    parse_args,
)
from common.steps_runner import run
from common.tele_notifier import send_file_to_telegram


class ReSampleData:
    def run(self, context):
        df = context["df"]
        context["hourly_df"] = resample_candles(df, "1H")


class CalculateIndicators(object):
    def run(self, context):
        df = context["hourly_df"]
        context["close"] = df["close"].iloc[-1]

        indicators = {}
        # RSI
        context["rsi_range"] = [4]
        for rsi in context["rsi_range"]:
            indicators[f"rsi_{rsi}"] = df[f"rsi_{rsi}"][-1]

        context["indicators"] = indicators
        logging.info(f"Close {context['close']} -> Indicators => {indicators}")


class GenerateChart:
    def run(self, context):
        df = context["hourly_df"]
        args = context["args"]
        chart_title = f"{args.coin}_{args.stable_coin}_60m"
        context["chart_name"] = chart_title
        context[
            "chart_file_path"
        ] = chart_file_path = f"output/{chart_title.lower()}-rsi.png"
        save = dict(fname=chart_file_path)
        fig, axes = mpf.plot(
            df,
            type="line",
            savefig=save,
            returnfig=True,
        )
        fig.savefig(save["fname"])


class IdentifyBuySellSignal(object):
    def _if_hit_stop_loss(self, actual_order_price, close_price, target_pct):
        if actual_order_price < 0:
            return False

        pct_change = (close_price - actual_order_price) / actual_order_price * 100
        sl_hit = "🔴" if pct_change < -1 * target_pct else "🤞"
        logging.info(
            f"Pct Change: {pct_change:.2f}%, Target Percent: (+/-){target_pct}%, SL Hit {sl_hit}"
        )
        return sl_hit

    def run(self, context):
        indicators = context["indicators"]
        args = context["args"]
        target_pct = args.target_pct
        last_transaction_order_details_price = context[
            "last_transaction_order_details_price"
        ]
        close = context["close"]
        rsi_4 = indicators["rsi_4"]

        if rsi_4 > 60 or self._if_hit_stop_loss(
            last_transaction_order_details_price, close, target_pct
        ):
            context["signal"] = TradeSignal.SELL
        elif rsi_4 < 20:
            context["signal"] = TradeSignal.BUY
        else:
            context["signal"] = TradeSignal.NO_SIGNAL

        logging.info(f"Identified signal => {context.get('signal')}")


class PublishStrategyChartOnTelegram:
    def run(self, context):
        trade_done = context.get("trade_done", False)
        if trade_done:
            chart_file_path = context["chart_file_path"]
            send_file_to_telegram("RSI", chart_file_path)


def main(args):
    init_logging()

    procedure = [
        SetupDatabase(),
        ReadConfiguration(),
        FetchDataFromExchange(),
        LoadDataInDataFrame(),
        ReSampleData(),
        FetchAccountInfoFromExchange(),
        LoadLastTransactionFromDatabase(),
        CalculateIndicators(),
        GenerateChart(),
        IdentifyBuySellSignal(),
        CheckIfIsANewSignal(),
        CalculateBuySellAmountBasedOnAllocatedPot(),
        ExecuteBuyTradeIfSignaled(),
        ExecuteSellTradeIfSignaled(),
        CollectInformationAboutOrder(),
        RecordTransactionInDatabase(),
        PublishTransactionOnTelegram(),
        PublishStrategyChartOnTelegram(),
    ]
    run(procedure, args)


if __name__ == "__main__":
    args = parse_args(__doc__)
    main(args)

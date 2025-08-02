from freqtrade.strategy import (
    IStrategy,
    BooleanParameter,
    DecimalParameter,
    IntParameter,
)
import talib.abstract as ta
import pandas as pd
from pandas import DataFrame


class MacdRsiEmaStrategy(IStrategy):
    """
    MACD RSI EMA Strategy
    
    This strategy combines three technical indicators:
    - MACD (Moving Average Convergence Divergence) for trend momentum
    - RSI (Relative Strength Index) for overbought/oversold conditions
    - EMA (Exponential Moving Average) for trend direction
    
    Entry conditions:
    - MACD histogram crosses above zero (bullish momentum)
    - RSI is above 50 (confirming upward momentum)
    - Fast EMA is above slow EMA (trend confirmation)
    - Volume confirmation
    
    Exit conditions:
    - RSI drops below 40 (momentum weakening)
    - OR MACD histogram turns negative for 2 consecutive periods
    """
    
    INTERFACE_VERSION = 3
    
    # Can this strategy go short?
    can_short: bool = False
    
    # Timeframe for the strategy
    timeframe = '1h'
    
    # Minimal ROI designed for the strategy
    minimal_roi = {
        "0": 0.05,
        "30": 0.03,
        "60": 0.01,
        "120": 0.0
    }
    
    # Optimal stoploss
    stoploss = -0.08
    
    # Trailing stoploss
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    
    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 30
    
    # Hyperoptable parameters
    rsi_buy_threshold = IntParameter(45, 65, default=50, space="buy")
    rsi_sell_threshold = IntParameter(30, 50, default=40, space="sell")
    ema_fast_period = IntParameter(3, 10, default=5, space="buy")
    ema_slow_period = IntParameter(15, 30, default=20, space="buy")
    
    # Optional order type mapping
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    
    # Optional order time in force
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}
    
    # Plot configuration
    plot_config = {
        "main_plot": {
            "ema5": {"color": "blue"},
            "ema20": {"color": "orange"},
        },
        "subplots": {
            "MACD": {
                "macd": {"color": "blue"},
                "macdsignal": {"color": "orange"},
                "macdhist": {"type": "bar", "plotly": {"opacity": 0.9}},
            },
            "RSI": {
                "rsi": {"color": "red"},
            },
        },
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds technical indicators to the given DataFrame
        
        :param dataframe: Dataframe with data from the exchange
        :param metadata: Additional information, like the currently traded pair
        :return: a Dataframe with all mandatory indicators for the strategies
        """
        # EMA - Exponential Moving Averages
        dataframe['ema5'] = ta.EMA(dataframe['close'], timeperiod=self.ema_fast_period.value)
        dataframe['ema20'] = ta.EMA(dataframe['close'], timeperiod=self.ema_slow_period.value)
        
        # RSI - Relative Strength Index
        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)
        
        # MACD - Moving Average Convergence Divergence
        macd_data = ta.MACD(dataframe['close'], fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe['macd'] = macd_data[0]
        dataframe['macdsignal'] = macd_data[1]
        dataframe['macdhist'] = macd_data[2]
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with entry columns populated
        """
        dataframe.loc[
            (
                # MACD histogram crosses above zero (bullish momentum)
                (dataframe['macdhist'] > 0) &
                (dataframe['macdhist'].shift(1) <= 0) &
                
                # RSI confirms upward momentum (adjusted threshold)
                (dataframe['rsi'] > self.rsi_buy_threshold.value) &
                
                # EMA trend confirmation
                (dataframe['ema5'] > dataframe['ema20']) &
                
                # Volume confirmation
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1
            
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with exit columns populated
        """
        dataframe.loc[
            (
                # Exit when RSI drops significantly (momentum weakening)
                (dataframe['rsi'] < self.rsi_sell_threshold.value) |
                
                # Exit when MACD histogram is negative for 2 consecutive periods
                ((dataframe['macdhist'] < 0) & 
                 (dataframe['macdhist'].shift(1) < 0))
            ),
            'exit_long'] = 1
            
        return dataframe
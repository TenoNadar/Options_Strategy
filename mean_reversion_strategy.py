"""
Mean Reversion Strategy for NIFTY Options (Intraday)

Strategy Logic:
- Uses 30-minute intraday moving average
- Buy Put (PE) when underlying is overbought (price > 30-min MA + 0.1%)
- Buy Call (CE) when underlying is oversold (price < 30-min MA - 0.1%)

This strategy assumes prices will revert to the intraday mean.
"""

import pandas as pd
import numpy as np

def get_entry_signal(date, current_underlying, date_data, backtest_framework):
    """
    Mean Reversion Entry Logic - Intraday 30-minute MA.
    
    Args:
        date: Current date
        current_underlying: Current underlying price
        date_data: Filtered data for the current date
        backtest_framework: Backtest framework instance
        
    Returns:
        tuple: (option_type, should_entry)
    """
    # Get all intraday data up to current point
    # date_data is already filtered to current and before, sorted by DateTime
    if len(date_data) == 0:
        return None, False
    
    current_datetime = date_data['DateTime'].iloc[-1]
    
    # Get data from last 30 data points (representing ~30 minutes)
    historical_intraday = date_data.copy()
    
    # Need at least 30 minutes of data
    if len(historical_intraday) < 30:
        return None, False
    
    # Calculate 30-minute moving average from intraday data
    historical_underlying = historical_intraday['UNDERLYING'].tail(30).mean()
    
    if pd.isna(historical_underlying) or historical_underlying <= 0:
        return None, False
    
    # Entry thresholds: very conservative 0.5% deviation for mean reversion
    upper_threshold = historical_underlying * 1.005
    lower_threshold = historical_underlying * 0.995
    
    # Overbought - Buy PE (expecting price to fall back to MA)
    # Only enter if deviation is very significant
    if current_underlying > upper_threshold:
        return 'PE', True
    # Oversold - Buy CE (expecting price to rise back to MA)
    elif current_underlying < lower_threshold:
        return 'CE', True
    
    return None, False


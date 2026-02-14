"""
Directional Strategy for NIFTY Options (Intraday)

Strategy Logic:
- Buy Call (CE) when underlying is in strong intraday uptrend (price > 20-min average by 0.15%)
- Buy Put (PE) when underlying is in strong intraday downtrend (price < 20-min average by 0.15%)

This strategy follows intraday momentum and trends.
"""

import pandas as pd
import numpy as np

def get_entry_signal(date, current_underlying, date_data, backtest_framework):
    """
    Directional Entry Logic - Intraday Momentum.
    
    Args:
        date: Current date
        current_underlying: Current underlying price
        date_data: Filtered data for the current date
        backtest_framework: Backtest framework instance
        
    Returns:
        tuple: (option_type, should_entry)
    """
    # Get all intraday data up to current point
    if len(date_data) == 0:
        return None, False
    
    current_datetime = date_data['DateTime'].iloc[-1]
    
    # Get historical intraday data
    historical_intraday = date_data.copy()
    
    # Need at least 20 minutes of data
    if len(historical_intraday) < 200:
        return None, False
    
    # Calculate 20-minute moving average
    recent_avg = historical_intraday['UNDERLYING'].tail(20).mean()
    
    if pd.isna(recent_avg) or recent_avg <= 0:
        return None, False
    
    # Momentum thresholds: 0.5% deviation - only strong trends
    upper_threshold = recent_avg * 1.085
    lower_threshold = recent_avg * 0.1125
    
    # Strong uptrend - Buy CE (expecting continuation up)
    # Require very strong confirmation
    if current_underlying > upper_threshold:
        return 'CE', True
    # Strong downtrend - Buy PE (expecting continuation down)
    elif current_underlying < lower_threshold:
        return 'PE', True
    
    return None, False


"""
Semi-Directional Strategy for NIFTY Options (Intraday)

Strategy Logic:
- Combines 30-minute mean reversion with momentum
- Buy PE when price is overbought (above 30-min MA) with positive momentum (contrarian)
- Buy CE when price is oversold (below 30-min MA) with negative momentum (contrarian)

This strategy uses mean reversion with momentum confirmation.
"""

import pandas as pd
import numpy as np

def get_entry_signal(date, current_underlying, date_data, backtest_framework):
    """
    Semi-Directional Entry Logic - Intraday 30-minute MA with momentum.
    
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
    
    if len(historical_intraday) < 30:
        return None, False
    
    # Calculate 30-minute moving average
    ma = historical_intraday['UNDERLYING'].tail(30).mean()
    
    if pd.isna(ma) or ma <= 0:
        return None, False
    
    # Calculate short-term momentum (comparing recent vs older prices)
    if len(historical_intraday) >= 10:
        recent_prices = historical_intraday['UNDERLYING'].tail(5)
        older_prices = historical_intraday['UNDERLYING'].tail(10).head(5)
        momentum = (recent_prices.mean() - older_prices.mean()) / older_prices.mean()
    else:
        momentum = 0
    
    # Overbought with positive momentum - Buy PE (contrarian)
    # Even more conservative - only trade strong signals
    if current_underlying > ma * 1.003 and momentum > 0.003:
        return 'PE', True
    
    # Oversold with negative momentum - Buy CE (contrarian)
    elif current_underlying < ma * 0.997 and momentum < -0.003:
        return 'CE', True
    
    return None, False


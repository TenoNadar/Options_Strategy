import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

class OptionsBacktestFramework:
    """
    Core backtesting framework for NIFTY options trading strategies.
    """
    def __init__(self, nifty_data, initial_capital=1000000):
        self.nifty_data = nifty_data
        self.initial_capital = initial_capital
        self.trades = []
    
    def get_nearest_expiry(self, current_date):
        """Get the expiry date with smallest DTE for a given date."""
        date_data = self.nifty_data[self.nifty_data['Date'] == current_date]
        if len(date_data) == 0:
            return None
        
        unique_expiries = date_data.groupby('Expiry')['DTE'].first()
        if len(unique_expiries) == 0:
            return None
        
        nearest_expiry = unique_expiries.idxmin()
        return nearest_expiry
    
    def get_atm_strike(self, underlying_price):
        """Round underlying price to nearest 50 for ATM strike."""
        if pd.isna(underlying_price) or underlying_price <= 0:
            return None
        return round(underlying_price / 50) * 50
    
    def get_option_price(self, date, expiry, strike, option_type):
        """Get option price for specific parameters."""
        date_data = self.nifty_data[
            (self.nifty_data['Date'] == date) &
            (self.nifty_data['Expiry'] == expiry) &
            (self.nifty_data['Strike'] == strike) &
            (self.nifty_data['Option Type'] == option_type)
        ]
        
        if len(date_data) == 0:
            return None
        
        return date_data.iloc[0]['Close']
    
    def get_exit_price_at_close(self, date, expiry, strike, option_type):
        """Get option price at 15:00:00 exit time."""
        date_data = self.nifty_data[
            (self.nifty_data['Date'] == date) &
            (self.nifty_data['Expiry'] == expiry) &
            (self.nifty_data['Strike'] == strike) &
            (self.nifty_data['Option Type'] == option_type)
        ]
        
        if len(date_data) == 0:
            return None
        
        close_time = pd.Timestamp(f"{date} 15:00:00")
        close_data = date_data[date_data['DateTime'] <= close_time]
        
        if len(close_data) > 0:
            return close_data.iloc[-1]['Close']
        
        return date_data.iloc[-1]['Close']
    
    def calculate_moving_average(self, current_date, window=3):
        """Calculate moving average of underlying price."""
        historical = self.nifty_data[self.nifty_data['Date'] < current_date]
        
        if len(historical) == 0:
            return None
        
        daily_data = historical.groupby('Date')['UNDERLYING'].first()
        
        if len(daily_data) < window:
            # Use all available data if less than window
            if len(daily_data) == 0:
                return None
            return daily_data.mean()
        
        return daily_data.tail(window).mean()
    
    def backtest_strategy(self, strategy_name, entry_logic):
        """
        Generic backtest function for any strategy.
        
        Args:
            strategy_name: Name of the strategy
            entry_logic: Function that returns (option_type, entry_signal) 
        """
        print(f"\nRunning {strategy_name} Strategy...")
        
        capital = self.initial_capital
        trades = []
        trades_today = {}
        live_positions = []
        entry_checks = 0
        
        # Iterate through each time point (for intraday trading)
        unique_dates = sorted(self.nifty_data['Date'].unique())
        print(f"  Processing {len(unique_dates)} unique dates for intraday trading...")
        
        # Track live positions
        for date in unique_dates:
            if date not in trades_today:
                trades_today[date] = 0
            
            date_filtered = self.nifty_data[self.nifty_data['Date'] == date]
            
            # Close positions at 15:00:00
            positions_to_close = []
            for i, pos in enumerate(live_positions):
                # Close positions opened on this or previous days
                if date >= pos['entry_date']:
                    exit_price = self.get_exit_price_at_close(
                        date, pos['expiry'], pos['strike'], pos['option_type']
                    )
                    
                    if exit_price is not None:
                        pnl_pct = (exit_price - pos['entry_price']) / pos['entry_price']
                        pnl = pos['investment'] * pnl_pct
                        capital += pnl
                        
                        trades.append({
                            'strategy': strategy_name,
                            'entry_date': pos['entry_date'],
                            'exit_date': date,
                            'entry_time': pos['entry_time'],
                            'exit_time': '15:00:00',
                            'option_type': pos['option_type'],
                            'strike': pos['strike'],
                            'expiry': pos['expiry'],
                            'entry_price': pos['entry_price'],
                            'exit_price': exit_price,
                            'profit': pnl,
                            'profit_pct': pnl_pct * 100,
                            'capital_after': capital,
                            'underlying_at_entry': pos.get('underlying_at_entry', 0)
                        })
                        positions_to_close.append(i)
                        trades_today[date] += 1
            
            for i in sorted(positions_to_close, reverse=True):
                if i < len(live_positions):
                    live_positions.pop(i)
            
            if len(positions_to_close) > 0:
                print(f"  Closed {len(positions_to_close)} positions on {date}")
            
            # Entry logic - iterate through intraday time points
            # Only check every 5 minutes to avoid too many checks
            for idx in range(0, len(date_filtered), 5):
                if len(live_positions) > 0 or trades_today[date] >= 3:
                    break
                
                intraday_row = date_filtered.iloc[idx]
                current_time = intraday_row['Time']
                
                # Skip entries before 9:30 AM (need at least 30 min of data for MA)
                try:
                    hour, minute = current_time.split(':')[:2]
                    if int(hour) < 9 or (int(hour) == 9 and int(minute) < 30):
                        continue
                except:
                    pass
                
                current_underlying = intraday_row['UNDERLYING']
                
                if pd.isna(current_underlying) or current_underlying <= 0:
                    continue
                
                expiry = self.get_nearest_expiry(date)
                
                if expiry is not None:
                    strike = self.get_atm_strike(current_underlying)
                    
                    if strike is None:
                        continue
                    
                    entry_checks += 1
                    # Pass current timepoint data for intraday analysis
                    current_data = date_filtered[date_filtered['DateTime'] <= intraday_row['DateTime']]
                    option_type, should_entry = entry_logic(date, current_underlying, current_data)
                    
                    if should_entry and option_type:
                        entry_price = self.get_option_price(date, expiry, strike, option_type)
                        
                        if entry_price is not None and entry_price > 0:
                            investment = capital * 0.1
                            
                            live_positions.append({
                                'entry_date': date,
                                'entry_time': current_time,
                                'expiry': expiry,
                                'strike': strike,
                                'option_type': option_type,
                                'entry_price': entry_price,
                                'investment': investment,
                                'underlying_at_entry': current_underlying
                            })
                            trades_today[date] += 1
                            print(f"    Trade entry: {date} at {current_time} - {option_type} at strike {strike}")
            
            # Close positions that were just opened on this date (intraday close at 15:00)
            positions_to_close = []
            for i, pos in enumerate(live_positions):
                if date == pos['entry_date']:
                    exit_price = self.get_exit_price_at_close(
                        date, pos['expiry'], pos['strike'], pos['option_type']
                    )
                    
                    if exit_price is not None:
                        pnl_pct = (exit_price - pos['entry_price']) / pos['entry_price']
                        pnl = pos['investment'] * pnl_pct
                        capital += pnl
                        
                        trades.append({
                            'strategy': strategy_name,
                            'entry_date': pos['entry_date'],
                            'exit_date': date,
                            'entry_time': pos['entry_time'],
                            'exit_time': '15:00:00',
                            'option_type': pos['option_type'],
                            'strike': pos['strike'],
                            'expiry': pos['expiry'],
                            'entry_price': pos['entry_price'],
                            'exit_price': exit_price,
                            'profit': pnl,
                            'profit_pct': pnl_pct * 100,
                            'capital_after': capital,
                            'underlying_at_entry': pos.get('underlying_at_entry', 0)
                        })
                        positions_to_close.append(i)
                        trades_today[date] += 1
            
            for i in sorted(positions_to_close, reverse=True):
                if i < len(live_positions):
                    live_positions.pop(i)
        
        print(f"  Entry checks: {entry_checks}, Trades generated: {len(trades)}")
        return pd.DataFrame(trades)
    
    def calculate_performance_metrics(self, trades_df):
        """Calculate comprehensive performance metrics."""
        if len(trades_df) == 0:
            return self._empty_metrics()
        
        trades_df = trades_df.sort_values('entry_date').reset_index(drop=True)
        
        # CAGR
        total_days = (trades_df['exit_date'].max() - trades_df['entry_date'].min()).days
        if total_days == 0:
            cagr = 0
        else:
            final_value = trades_df['capital_after'].iloc[-1]
            cagr = ((final_value / self.initial_capital) ** (365.25 / total_days) - 1) * 100
        
        # Equity curve for drawdown calculation
        equity_curve = []
        capital = self.initial_capital
        
        for idx, trade in trades_df.iterrows():
            capital = trade['capital_after']
            equity_curve.append({
                'date': trade['exit_date'],
                'capital': capital
            })
        
        equity_df = pd.DataFrame(equity_curve)
        equity_df['cumulative'] = equity_df['capital'] / equity_df['capital'].iloc[0]
        equity_df['running_max'] = equity_df['cumulative'].expanding().max()
        equity_df['drawdown'] = (equity_df['cumulative'] - equity_df['running_max']) / equity_df['running_max']
        mdd = equity_df['drawdown'].min() * 100
        
        # Sharpe Ratio
        equity_df['returns'] = equity_df['capital'].pct_change()
        returns = equity_df['returns'].dropna()
        sharpe = 0
        if len(returns) > 0 and returns.std() > 0:
            sharpe = np.sqrt(252) * returns.mean() / returns.std()
        
        # Win rate and stats
        winning_trades = trades_df[trades_df['profit'] > 0]
        losing_trades = trades_df[trades_df['profit'] <= 0]
        
        win_rate = (len(winning_trades) / len(trades_df)) * 100 if len(trades_df) > 0 else 0
        avg_profit = winning_trades['profit'].mean() if len(winning_trades) > 0 else 0
        avg_loss = losing_trades['profit'].mean() if len(losing_trades) > 0 else 0
        
        # Profit Factor
        total_profit = winning_trades['profit'].sum() if len(winning_trades) > 0 else 0
        total_loss = abs(losing_trades['profit'].sum()) if len(losing_trades) > 0 else 1
        profit_factor = total_profit / total_loss if total_loss > 0 else 0
        
        # Max consecutive wins/losses
        trades_df['result'] = trades_df['profit'].apply(lambda x: 1 if x > 0 else -1)
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_wins = 0
        current_losses = 0
        
        for result in trades_df['result']:
            if result == 1:
                current_wins += 1
                current_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, current_losses)
        
        return {
            'CAGR (%)': cagr,
            'Maximum_Drawdown (%)': mdd,
            'Sharpe_Ratio': sharpe,
            'Win_Rate (%)': win_rate,
            'Total_Trades': len(trades_df),
            'Winning_Trades': len(winning_trades),
            'Losing_Trades': len(losing_trades),
            'Avg_Profit_Per_Trade': avg_profit,
            'Avg_Loss_Per_Trade': avg_loss,
            'Total_Return (%)': ((trades_df['capital_after'].iloc[-1] / self.initial_capital) - 1) * 100,
            'Final_Capital': trades_df['capital_after'].iloc[-1],
            'Profit_Factor': profit_factor,
            'Max_Consecutive_Wins': max_consecutive_wins,
            'Max_Consecutive_Losses': max_consecutive_losses,
            'Equity_Curve': equity_df
        }
    
    def _empty_metrics(self):
        """Return empty metrics."""
        return {
            'CAGR (%)': 0,
            'Maximum_Drawdown (%)': 0,
            'Sharpe_Ratio': 0,
            'Win_Rate (%)': 0,
            'Total_Trades': 0,
            'Winning_Trades': 0,
            'Losing_Trades': 0,
            'Avg_Profit_Per_Trade': 0,
            'Avg_Loss_Per_Trade': 0,
            'Total_Return (%)': 0,
            'Final_Capital': self.initial_capital,
            'Profit_Factor': 0,
            'Max_Consecutive_Wins': 0,
            'Max_Consecutive_Losses': 0,
            'Equity_Curve': pd.DataFrame()
        }


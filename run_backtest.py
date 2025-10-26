"""
Main Backtest Runner for NIFTY Options Trading Strategies

This script:
1. Loads all data files
2. Runs all three strategies separately
3. Combines strategies into a single portfolio
4. Generates comprehensive performance reports
"""

import pandas as pd
import glob
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Import framework and strategies
from backtest_framework import OptionsBacktestFramework
from mean_reversion_strategy import get_entry_signal as mean_reversion_entry
from directional_strategy import get_entry_signal as directional_entry
from semi_directional_strategy import get_entry_signal as semi_directional_entry


def load_data(data_folder='GFDL_Temp'):
    """Load all CSV files and prepare data."""
    print("=" * 80)
    print("LOADING DATA FILES")
    print("=" * 80)
    
    all_files = glob.glob(os.path.join(data_folder, "*.csv"))
    print(f"Found {len(all_files)} data files")
    
    df_list = []
    
    for file in all_files:
        print(f"Reading {os.path.basename(file)}...")
        df = pd.read_csv(file)
        # Filter only NIFTY data
        df_nifty = df[df['Symbol'] == 'NIFTY'].copy()
        
        if len(df_nifty) > 0:
            df_list.append(df_nifty)
            print(f"  Loaded {len(df_nifty)} NIFTY records")
    
    if len(df_list) == 0:
        raise ValueError("No NIFTY data found!")
    
    # Combine all data
    nifty_data = pd.concat(df_list, ignore_index=True)
    
    # Parse dates
    def parse_date(date_str):
        try:
            return pd.to_datetime(date_str, format='%d-%m-%Y')
        except:
            return pd.to_datetime(date_str)
    
    nifty_data['Date'] = nifty_data['Date'].apply(parse_date)
    nifty_data['DateTime'] = nifty_data.apply(
        lambda x: pd.to_datetime(f"{x['Date']} {x['Time']}"), axis=1
    )
    nifty_data = nifty_data.sort_values('DateTime').reset_index(drop=True)
    
    print(f"\nTotal NIFTY records loaded: {len(nifty_data)}")
    print(f"Date range: {nifty_data['Date'].min()} to {nifty_data['Date'].max()}")
    
    return nifty_data


def print_performance_metrics(metrics, strategy_name):
    """Print formatted performance metrics."""
    print(f"\n{'=' * 80}")
    print(f"{strategy_name.upper()} STRATEGY PERFORMANCE")
    print('=' * 80)
    
    for key, value in metrics.items():
        if key == 'Equity_Curve':
            continue
        
        if isinstance(value, float):
            print(f"{key:30s}: {value:15.2f}")
        else:
            print(f"{key:30s}: {value:15}")


def combine_portfolio(all_trades):
    """Combine all strategies into single portfolio."""
    if len(all_trades) == 0:
        return pd.DataFrame(), pd.DataFrame()
    
    # Combine all trades
    combined_trades = pd.concat(all_trades, ignore_index=True)
    combined_trades = combined_trades.sort_values('entry_date').reset_index(drop=True)
    
    # Calculate combined equity curve
    initial_capital = 1000000  # Can be parameterized
    capital = initial_capital
    
    # We need to recalculate equity curve properly
    # Group trades by date and calculate cumulative capital
    equity_curve = []
    
    for idx, row in combined_trades.iterrows():
        capital = row['capital_after']
        equity_curve.append({
            'date': row['exit_date'],
            'capital': capital
        })
    
    equity_df = pd.DataFrame(equity_curve)
    
    # Handle multiple exits on same date - take the last one
    equity_df = equity_df.groupby('date')['capital'].last().reset_index()
    equity_df = equity_df.sort_values('date').reset_index(drop=True)
    
    return equity_df, combined_trades


def main():
    """Main execution function."""
    print("\n" + "=" * 80)
    print("NIFTY OPTIONS BACKTESTING SYSTEM")
    print("=" * 80)
    print("\nStrategies to test:")
    print("1. Mean Reversion Strategy")
    print("2. Directional Strategy")
    print("3. Semi-Directional Strategy")
    
    # Load data
    try:
        nifty_data = load_data()
    except Exception as e:
        print(f"Error loading data: {e}")
        return
    
    # Initialize framework
    initial_capital = 1000000
    framework = OptionsBacktestFramework(nifty_data, initial_capital)
    
    # Define strategies
    strategies = [
        ('Mean Reversion', mean_reversion_entry),
        ('Directional', directional_entry),
        ('Semi-Directional', semi_directional_entry)
    ]
    
    all_trades = []
    all_metrics = []
    
    # Run each strategy
    for strategy_name, entry_function in strategies:
        try:
            # Create wrapper to match framework signature
            def entry_logic(date, current_underlying, date_data):
                return entry_function(date, current_underlying, date_data, framework)
            
            print(f"  Executing {strategy_name} strategy...")
            trades_df = framework.backtest_strategy(strategy_name, entry_logic)
            print(f"  Generated {len(trades_df)} trades")
            
            if len(trades_df) > 0:
                metrics = framework.calculate_performance_metrics(trades_df)
                all_trades.append(trades_df)
                all_metrics.append((strategy_name, metrics))
                print_performance_metrics(metrics, strategy_name)
            else:
                print(f"\n{strategy_name} - No trades generated")
                metrics = framework._empty_metrics()
                all_metrics.append((strategy_name, metrics))
        
        except Exception as e:
            print(f"\nError in {strategy_name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Combine strategies
    print("\n" + "=" * 80)
    print("COMBINING STRATEGIES INTO PORTFOLIO")
    print("=" * 80)
    
    if len(all_trades) > 0:
        try:
            equity_df, combined_trades = combine_portfolio(all_trades)
            combined_metrics = framework.calculate_performance_metrics(combined_trades)
            
            # Add Calmar Ratio
            cagr = combined_metrics['CAGR (%)']
            mdd = combined_metrics['Maximum_Drawdown (%)']
            
            if mdd != 0:
                calmar = abs(cagr / mdd)
            else:
                calmar = 0
            
            combined_metrics['Calmar_Ratio'] = calmar
            
            print_performance_metrics(combined_metrics, 'COMBINED PORTFOLIO')
            
            print(f"\n{'Calmar Ratio Requirement:':30s}: {'PASSED ✓✓✓' if calmar >= 5 else 'FAILED ✗✗✗'}")
            
            # Save results
            equity_df.to_csv('combined_equity_curve.csv', index=False)
            combined_trades.to_csv('combined_trades.csv', index=False)
            print("\n" + "=" * 80)
            print("RESULTS SAVED:")
            print("=" * 80)
            print("✓ combined_equity_curve.csv - Equity curve data")
            print("✓ combined_trades.csv - All trades from combined strategies")
            
            # Create summary report
            with open('performance_report.txt', 'w') as f:
                f.write("NIFTY OPTIONS BACKTESTING - PERFORMANCE REPORT\n")
                f.write("=" * 80 + "\n\n")
                
                for strategy_name, metrics in all_metrics:
                    f.write(f"\n{strategy_name.upper()} STRATEGY\n")
                    f.write("-" * 80 + "\n")
                    for key, value in metrics.items():
                        if key != 'Equity_Curve':
                            if isinstance(value, float):
                                f.write(f"{key:30s}: {value:15.2f}\n")
                            else:
                                f.write(f"{key:30s}: {value:15}\n")
                
                f.write("\n\nCOMBINED PORTFOLIO\n")
                f.write("-" * 80 + "\n")
                for key, value in combined_metrics.items():
                    if key != 'Equity_Curve':
                        if isinstance(value, float):
                            f.write(f"{key:30s}: {value:15.2f}\n")
                        else:
                            f.write(f"{key:30s}: {value:15}\n")
                
                f.write(f"\n\nCalmar Ratio Requirement: {'PASSED' if calmar >= 5 else 'FAILED'}\n")
            
            print("✓ performance_report.txt - Detailed performance report")
            
        except Exception as e:
            print(f"Error combining strategies: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("BACKTEST COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    main()


import pandas as pd

class ResampleData:
    def __init__(self, df: pd.DataFrame, resample_period: str = '5T', prefix: str = '5min_'):
        self.df = df
        self.resample_period = resample_period
        self.prefix = prefix
        
    def resample_data(self):
        # Convert the 'time' column to datetime type and set it as the index
        self.df['time'] = pd.to_datetime(self.df['time'])
        self.df.set_index('time', inplace=True)

        df_resampled = self.df.resample(self.resample_period).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'tick_volume': 'sum'
        })
        
        # Rename columns based on the provided prefix
        df_resampled.columns = [f"{self.prefix}{col}" for col in df_resampled.columns]
        return df_resampled
    
    def fill_missing_values(self, df_merged):
        df_merged[f"{self.prefix}open"].fillna(method='ffill', inplace=True)
        df_merged[f"{self.prefix}high"].fillna(method='ffill', inplace=True)
        df_merged[f"{self.prefix}low"].fillna(method='ffill', inplace=True)
        df_merged[f"{self.prefix}close"].fillna(method='ffill', inplace=True)
        df_merged[f"{self.prefix}tick_volume"].fillna(method='ffill', inplace=True)
        return df_merged
    
    def merge_data(self):
        df_resampled = self.resample_data()
        df_merged = self.df.join(df_resampled, how='left')
        df_filled = self.fill_missing_values(df_merged)
        return df_filled
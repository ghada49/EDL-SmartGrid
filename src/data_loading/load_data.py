# /src/data_loading/load_data.py
import pandas as pd
import numpy as np
from scipy.stats import zscore

class DataLoader:
    def __init__(self, file_path):
        """
        Initializes the DataLoader with the file path.
        
        Args:
        file_path (str): Path to the raw data file (CSV, Excel, etc.)
        """
        self.file_path = file_path
        self.df = None

    def load_data(self):
        """
        Loads the data from the specified file.
        
        Returns:
        pd.DataFrame: Loaded data
        """
        if self.file_path.endswith('.csv'):
            self.df = pd.read_csv(self.file_path)
        elif self.file_path.endswith('.xlsx'):
            self.df = pd.read_excel(self.file_path)
        else:
            raise ValueError("Unsupported file format. Please use CSV or Excel.")
        
        print(f"Data loaded from {self.file_path}")
        return self.df

    def explore_data(self):
        """
        Basic exploration of the dataset to print information and initial stats.
        
        Prints:
        - Dataframe info (columns, non-null counts, data types)
        - Basic summary statistics
        """
        print("\nData Overview:")
        print(self.df.info())
        print("\nFirst few rows of the data:")
        print(self.df.head())
        print("\nSummary Statistics:")
        print(self.df.describe())
        
    def handle_missing_values(self):
        """
        Identifies and handles missing values in the dataframe.
        For numerical columns, it replaces NaN values with the median of the column.
        """
        missing_values = self.df.isnull().sum()
        print(f"\nMissing values per column:\n{missing_values}")
        
        # Handling missing values by filling NaNs with the median value
        self.df.fillna(self.df.median(), inplace=True)
        print("\nMissing values handled (filled with median).")
        return self.df

    def remove_duplicates(self):
        """
        Remove duplicate rows from the dataset.
        """
        duplicates = self.df.duplicated().sum()
        print(f"\nNumber of duplicate rows: {duplicates}")
        
        if duplicates > 0:
            self.df = self.df.drop_duplicates()
            print(f"Duplicate rows removed.")
        return self.df
    
    def detect_outliers_zscore(self, threshold=3):
        """
        Detect outliers using the Z-score method. Rows with |Z| > threshold are considered outliers.
        
        Args:
        threshold (int or float): Z-score threshold for detecting outliers (default 3).
        
        Returns:
        pd.DataFrame: DataFrame with outliers based on Z-score.
        """
        # Apply Z-score on the 'Total electricity consumption (kWh)' column
        self.df['zscore'] = zscore(self.df['Total electricity consumption (kWh)'])
        
        outliers = self.df[np.abs(self.df['zscore']) > threshold]
        print(f"\nOutliers detected using Z-score (|Z| > {threshold}):\n", outliers)
        return outliers
    
    def detect_outliers_iqr(self):
        """
        Detect outliers using the IQR (Interquartile Range) method.
        
        Returns:
        pd.DataFrame: DataFrame with outliers based on IQR method.
        """
        Q1 = self.df['Total electricity consumption (kWh)'].quantile(0.25)
        Q3 = self.df['Total electricity consumption (kWh)'].quantile(0.75)
        IQR = Q3 - Q1
        
        outliers = self.df[(self.df['Total electricity consumption (kWh)'] < Q1 - 1.5 * IQR) | 
                           (self.df['Total electricity consumption (kWh)'] > Q3 + 1.5 * IQR)]
        print("\nOutliers detected using IQR method:\n", outliers)
        return outliers

    def check_skewness(self):
        """
        Check for skewness in the numerical columns.
        
        Returns:
        pd.Series: Skewness values for each numerical feature.
        """
        skewness = self.df.select_dtypes(include=[np.number]).skew()
        print("\nSkewness for each numerical feature:\n", skewness)
        return skewness

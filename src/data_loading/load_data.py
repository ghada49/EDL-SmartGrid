import pandas as pd
import numpy as np
from scipy.stats import zscore
import os, sys

class DataLoader:
    def __init__(self, file_path):
        """
        Initializes the DataLoader with the file path.

        Args:
            file_path (str): Path to the raw data file (CSV, Excel, etc.)
        """
        self.file_path = file_path
        self.df = None

    # -------------------------------
    # DATA LOADING
    # -------------------------------
    def load_data(self):
        """Loads the data from the specified file."""
        if self.file_path.endswith('.csv'):
            self.df = pd.read_csv(self.file_path)
        elif self.file_path.endswith('.xlsx'):
            self.df = pd.read_excel(self.file_path)
        else:
            raise ValueError("Unsupported file format. Please use CSV or Excel.")

        print(f"[OK] Data loaded successfully from {self.file_path}")
        return self.df

    # -------------------------------
    # EXPLORATION
    # -------------------------------
    def explore_data(self):
        """Displays information, basic stats, and first few rows."""
        print("\n[DATA] Data Overview:")
        print(self.df.info())

        print("\n[INFO] First 5 Rows:")
        print(self.df.head())

        print("\n[STATS] Summary Statistics (Numerical Columns):")
        print(self.df.describe())

        print("\n[COLS] Columns:")
        print(list(self.df.columns))

    # -------------------------------
    # DATA CLEANING
    # -------------------------------
    def handle_missing_values(self):
        """Fills NaNs with median for numeric columns, mode for categorical."""
        print("\n🧩 Missing Values per Column:")
        print(self.df.isnull().sum())

        # Fill numeric NaNs with median
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        self.df[numeric_cols] = self.df[numeric_cols].fillna(self.df[numeric_cols].median())

        # Fill non-numeric NaNs with mode
        non_numeric_cols = self.df.select_dtypes(exclude=[np.number]).columns
        for col in non_numeric_cols:
            if self.df[col].isnull().any():
                self.df[col].fillna(self.df[col].mode()[0], inplace=True)

        print("\n[OK] Missing values handled (numeric -> median, categorical -> mode).")
        return self.df

    def report_duplicates(self):
        """Reports number of duplicate rows (does not remove them)."""
        duplicates = self.df.duplicated().sum()
        print(f"\n🧹 Number of duplicate rows in dataset: {duplicates}")
        print(f"[COLS] Total rows (including duplicates): {len(self.df)}")
        return duplicates

    # -------------------------------
    # OUTLIER DETECTION
    # -------------------------------
    def detect_outliers_zscore(self, threshold=3):
        """Detects outliers using Z-score for all numeric columns."""
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            print("\n[WARN] No numeric columns to apply Z-score.")
            return pd.DataFrame()

        z_scores = np.abs(zscore(self.df[numeric_cols]))
        outliers = self.df[(z_scores > threshold).any(axis=1)]
        print(f"\n[WARN] Outliers detected using Z-score (|Z| > {threshold}): {len(outliers)} rows")
        return outliers

    def detect_outliers_iqr(self):
        """Detects outliers using IQR for all numeric columns."""
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            print("\n[WARN] No numeric columns to apply IQR method.")
            return pd.DataFrame()

        outlier_indices = set()
        for col in numeric_cols:
            Q1 = self.df[col].quantile(0.25)
            Q3 = self.df[col].quantile(0.75)
            IQR = Q3 - Q1
            mask = (self.df[col] < Q1 - 1.5 * IQR) | (self.df[col] > Q3 + 1.5 * IQR)
            outlier_indices.update(self.df[mask].index)

        outliers = self.df.loc[list(outlier_indices)]
        print(f"\n[WARN] Outliers detected using IQR: {len(outliers)} rows")
        return outliers

    # -------------------------------
    # NUMERICAL ANALYSIS
    # -------------------------------
    def check_skewness(self):
        """Computes skewness for numeric features."""
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            print("\n[WARN] No numeric columns to compute skewness.")
            return pd.Series()
        skewness = self.df[numeric_cols].skew()
        print("\n[DATA] Skewness for each numerical column:\n", skewness)
        return skewness

    def correlation_matrix(self):
        """Computes correlation matrix for numeric columns."""
        corr = self.df.corr(numeric_only=True)
        print("\n🔗 Correlation Matrix:\n", corr)
        return corr


# -------------------------------
# EXECUTION (MAIN)
# -------------------------------
if __name__ == "__main__":
    # Add parent directory for imports
    sys.path.append(os.path.abspath(os.path.join(os.getcwd(), '..')))

    # Dynamically build the path to data/raw/data.xlsx
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    file_path = os.path.join(base_dir, 'data', 'raw', 'data.xlsx')

    loader = DataLoader(file_path)
    df = loader.load_data()
    loader.explore_data()
    loader.handle_missing_values()
    loader.report_duplicates()
    loader.check_skewness()
    loader.correlation_matrix()

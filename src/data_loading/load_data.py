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

        print(f"✅ Data loaded successfully from {self.file_path}")
        return self.df

    # -------------------------------
    # EXPLORATION
    # -------------------------------
    def explore_data(self):
        """Displays information, basic stats, and first few rows."""
        print("\n📊 Data Overview:")
        print(self.df.info())

        print("\n🔍 First 5 Rows:")
        print(self.df.head())

        print("\n📈 Summary Statistics (Numerical Columns):")
        print(self.df.describe())

        print("\n📏 Columns:")
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

        print("\n✅ Missing values handled (numeric → median, categorical → mode).")
        return self.df

    def report_duplicates(self):
        """Reports number of duplicate rows (does not remove them)."""
        duplicates = self.df.duplicated().sum()
        print(f"\n🧹 Number of duplicate rows in dataset: {duplicates}")
        print(f"📏 Total rows (including duplicates): {len(self.df)}")
        return duplicates

    # -------------------------------
    # OUTLIER DETECTION
    # -------------------------------
    def detect_outliers_zscore(self, threshold=3):
        """Detects outliers using Z-score for all numeric columns."""
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            print("\n⚠️ No numeric columns to apply Z-score.")
            return pd.DataFrame()

        z_scores = np.abs(zscore(self.df[numeric_cols]))
        outliers = self.df[(z_scores > threshold).any(axis=1)]
        print(f"\n⚠️ Outliers detected using Z-score (|Z| > {threshold}): {len(outliers)} rows")
        return outliers

    def detect_outliers_iqr(self):
        """Detects outliers using IQR for all numeric columns."""
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            print("\n⚠️ No numeric columns to apply IQR method.")
            return pd.DataFrame()

        outlier_indices = set()
        for col in numeric_cols:
            Q1 = self.df[col].quantile(0.25)
            Q3 = self.df[col].quantile(0.75)
            IQR = Q3 - Q1
            mask = (self.df[col] < Q1 - 1.5 * IQR) | (self.df[col] > Q3 + 1.5 * IQR)
            outlier_indices.update(self.df[mask].index)

        outliers = self.df.loc[list(outlier_indices)]
        print(f"\n⚠️ Outliers detected using IQR: {len(outliers)} rows")
        return outliers

    # -------------------------------
    # NUMERICAL ANALYSIS
    # -------------------------------
    def check_skewness(self):
        """Computes skewness for numeric features."""
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            print("\n⚠️ No numeric columns to compute skewness.")
            return pd.Series()
        skewness = self.df[numeric_cols].skew()
        print("\n📊 Skewness for each numerical column:\n", skewness)
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

'''
Output for raw data when running this script:
✅ Data loaded successfully from c:\Users\HP\EECE-490-Project\data\raw\data.xlsx

📊 Data Overview:
<class 'pandas.core.frame.DataFrame'>
RangeIndex: 1761 entries, 0 to 1760
Data columns (total 8 columns):
 #   Column                               Non-Null Count  Dtype  
---  ------                               --------------  -----  
 0   FID                                  1761 non-null   int64  
 1   Building Construction Year           1761 non-null   int64  
 2   Number of floors                     1761 non-null   int64  
 3   Number of Apartments                 1761 non-null   int64  
 4   Total Electricity Consumption (kwH)  1761 non-null   float64
 5   Latitude                             1761 non-null   float64
 6   Longitude                            1761 non-null   float64
 7   Area in m^2                          1761 non-null   float64
dtypes: float64(4), int64(4)
memory usage: 110.2 KB
None

🔍 First 5 Rows:
   FID  Building Construction Year  ...  Longitude  Area in m^2
0    0                        1936  ...  33.892128   149.034627       
1    1                        1930  ...  33.894906   254.431544       
2    2                        1930  ...  33.894987   254.067839       
3    3                        1920  ...  33.891896    65.391169       
4    4                        1970  ...  33.889256   147.933395       

[5 rows x 8 columns]

📈 Summary Statistics (Numerical Columns):
               FID  ...  Area in m^2
count  1761.000000  ...  1761.000000
mean    880.000000  ...   212.949974
std     508.501229  ...   132.954190
min       0.000000  ...    28.112263
25%     440.000000  ...   120.466146
50%     880.000000  ...   185.273596
75%    1320.000000  ...   274.177729
max    1760.000000  ...  1180.263390

[8 rows x 8 columns]

📏 Columns:
['FID', 'Building Construction Year', 'Number of floors', 'Number of Apartments', 'Total Electricity Consumption (kwH)', 'Latitude', 'Longitude', 'Area in m^2']

🧩 Missing Values per Column:
FID                                    0
Building Construction Year             0
Number of floors                       0
Number of Apartments                   0
Total Electricity Consumption (kwH)    0
Latitude                               0
Longitude                              0
Area in m^2                            0
dtype: int64

✅ Missing values handled (numeric → median, categorical → mode).

🧹 Number of duplicate rows in dataset: 0
📏 Total rows (including duplicates): 1761

📊 Skewness for each numerical column:
 FID                                    0.000000
Building Construction Year            -8.790279
Number of floors                       1.543842
Number of Apartments                   7.025745
Total Electricity Consumption (kwH)    5.699579
Latitude                              -1.224980
Longitude                             -0.635503
Area in m^2                            1.823400
dtype: float64

🔗 Correlation Matrix:
                                           FID  ...  Area in m^2
FID                                  1.000000  ...    -0.038191
Building Construction Year          -0.146239  ...     0.277329
Number of floors                    -0.170448  ...     0.432800
Number of Apartments                -0.157525  ...     0.388391
Total Electricity Consumption (kwH) -0.032261  ...     0.350627
Latitude                             0.345641  ...    -0.358696
Longitude                           -0.091837  ...     0.009076
Area in m^2                         -0.038191  ...     1.000000

'''
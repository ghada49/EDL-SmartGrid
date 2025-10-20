# /src/data_loading/feature_engineering.py
import numpy as np
from sklearn.preprocessing import PowerTransformer

class FeatureEngineering:
    def __init__(self, df):
        self.df = df

    def add_age(self):
        """Add 'age' feature: 2017 - construction year."""
        self.df['age'] = 2017 - self.df["Building's construction year"]
        print("Age feature added")
        
        # Drop 'Building's construction year' since 'age' is derived from it
        self.df.drop(columns=["Building's construction year"], inplace=True)
        print("Dropped 'Building's construction year' column")
        
        return self.df

    def add_kwh_per_features(self):
        """Add 'kwh_per_apartment', 'kwh_per_floor'."""
        self.df['kwh_per_apartment'] = self.df['Total electricity consumption (kWh)'] / self.df['Number of apartments']
        self.df['kwh_per_floor'] = self.df['Total electricity consumption (kWh)'] / self.df['Number of floors']
        self.df['apartments_per_floor'] = self.df['Number of apartments'] / self.df['Number of floors']
        print("kwh_per_apartment, kwh_per_floor, and apartments_per_floor features added")
        return self.df

    def handle_skewness(self):
        """Handle skewed data by applying log transformation and PowerTransformer."""
        # Drop the 'Unnamed: 0' column if it exists
        if 'Unnamed: 0' in self.df.columns:
            self.df.drop(columns=['Unnamed: 0'], inplace=True)
            print("Dropped 'Unnamed: 0' column.")
        
        # Apply log transformation for 'Total electricity consumption (kWh)' to handle skewness
        self.df['log_kwh'] = np.log(self.df['Total electricity consumption (kWh)'] + 1)  # Adding 1 to avoid log(0)
        print("Log transformation applied to 'Total electricity consumption (kWh)'.")
        
        # Apply log transformation for 'Number of apartments' to handle skewness
        self.df['log_apartments'] = np.log(self.df['Number of apartments'] + 1)
        print("Log transformation applied to 'Number of apartments'.")
        
        # Apply log transformation for 'Number of floors' (optional, if needed)
        if self.df['Number of floors'].skew() > 1:
            self.df['log_floors'] = np.log(self.df['Number of floors'] + 1)
            print("Log transformation applied to 'Number of floors'.")

        # Apply Power Transformation (Yeo-Johnson) for other highly skewed features
        transformer = PowerTransformer(method='yeo-johnson')  # Can handle both positive and negative skew
        self.df[['log_kwh', 'log_apartments', 'log_floors']] = transformer.fit_transform(self.df[['log_kwh', 'log_apartments', 'log_floors']])
        print("Power transformation (Yeo-Johnson) applied to 'log_kwh', 'log_apartments', and 'log_floors'.")

        # Drop the original columns after log transformation
        self.df.drop(columns=['Total electricity consumption (kWh)', 'Number of apartments', 'Number of floors'], inplace=True)
        print("Dropped original columns after applying log transformation.")
        
        return self.df

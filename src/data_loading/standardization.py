import pandas as pd
from sklearn.preprocessing import StandardScaler

def standardize_data(df, columns):
    """
    Standardizes the specified columns in the dataframe.
    """
    if all(col in df.columns for col in columns):
        scaler = StandardScaler()
        df[columns] = scaler.fit_transform(df[columns])
    return df
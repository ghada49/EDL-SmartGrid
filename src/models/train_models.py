# /src/models/train_models.py

from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import joblib
import pandas as pd

def load_data(file_path):
    """Load the preprocessed data."""
    df = pd.read_csv(file_path)
    return df

def train_isolation_forest(df, features, contamination=0.05):
    """Train Isolation Forest model on the provided data."""
    # Extract features from the dataframe
    X = df[features]

    # Split the data into training and testing sets
    X_train, X_test = train_test_split(X, test_size=0.2, random_state=42)

    # Initialize the Isolation Forest model
    iso_forest = IsolationForest(n_estimators=100, contamination=contamination, random_state=42)

    # Train the model on the training data
    iso_forest.fit(X_train)

    # Predict anomalies on the test data
    y_test_pred = iso_forest.predict(X_test)
    y_test_pred = [1 if x == -1 else 0 for x in y_test_pred]  # Convert -1 to 1 (anomaly) and 1 to 0 (normal)

    # Print evaluation metrics
    print("Classification Report on Test Data:")
    print(classification_report(y_test_pred, y_test_pred))  # Add actual labels if available

    # Save the trained model to a file
    joblib.dump(iso_forest, 'data/model/isolation_forest_model.pkl')
    print("Model saved to 'data/model/isolation_forest_model.pkl'")

    # Return the trained model
    return iso_forest

if __name__ == "__main__":
    # Load the data (assuming data is already preprocessed and saved)
    file_path = 'data/processed/processed_data.csv'  # Modify this path as needed
    df = load_data(file_path)

    # Features for anomaly detection
    features = ['log_kwh', 'log_apartments','log_kwh_per_apartment',  'log_age','Longitude','Latitude']

    # Train the Isolation Forest model
    model = train_isolation_forest(df, features)

import pandas as pd
import pickle
from haversine import haversine, Unit

# Load new data and fixed warehouse data
new_data = pd.read_csv('new_data_with_categories.csv')
fixed_warehouse = pd.read_csv('fixed_warehouse.csv')

# Load the saved model and scaler
with open('warehouse_model.pkl', 'rb') as f:
    model_data = pickle.load(f)
    model = model_data['model']
    scaler = model_data['scaler']
    warehouses = model_data['warehouses']

# Merge coordinates (handle missing districts)
merged_data = pd.merge(
    new_data,
    fixed_warehouse[['District', 'Latitude', 'Longitude']],
    on='District',
    how='left'
)

# Check for missing coordinates
print("Districts with missing coordinates:")
print(merged_data[merged_data['Latitude'].isna() | merged_data['Longitude'].isna()]['District'].unique())

# Remove rows with missing coordinates
clean_data = merged_data.dropna(subset=['Latitude', 'Longitude']).copy()

# Calculate distances (only for valid coordinates)
def calculate_distances(row):
    return [
        haversine((row['Latitude'], row['Longitude']), 
                 (wh['Latitude'], wh['Longitude']), unit=Unit.KILOMETERS)
        for _, wh in warehouses.iterrows()
    ]

# Create distance matrix
new_distances = clean_data.apply(calculate_distances, axis=1)
distance_df = pd.DataFrame(
    new_distances.tolist(),
    columns=warehouses['District']
)

# Scale features and predict
scaled_data = scaler.transform(distance_df)
clean_data['Optimal Warehouse'] = [warehouses.iloc[cluster]['District'] 
                                  for cluster in model.predict(scaled_data)]

# Get significant warehouses (top 25%)
warehouse_counts = clean_data['Optimal Warehouse'].value_counts()
threshold = warehouse_counts.quantile(0.75)
significant_warehouses = warehouse_counts[warehouse_counts >= threshold].index.tolist()
import os
import pandas as pd

# Define the folder path containing CSV files
folder_path = 'edn2'

# Initialize an empty list to store rows with the value 0.1 in the first column
selected_rows = []

# Loop through each file in the folder
for filename in os.listdir(folder_path):
    if filename.endswith(".csv"):
        file_path = os.path.join(folder_path, filename)
        
        # Read the CSV file, skipping the first 6 rows
        df = pd.read_csv(file_path, skiprows=1051)
        
        # Check if any row in the first column has the value 0.1
        rows_with_0_1 = df[df.iloc[:, 1] == 0.1]
        
        # Append the selected rows to the list
        selected_rows.extend(rows_with_0_1.values.tolist())

# Create a DataFrame from the selected rows
extracted_data = pd.DataFrame(selected_rows)

# Save the extracted data to a CSV file
extracted_data.to_csv("S3-extracted_data.csv", index=False)

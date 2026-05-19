# -*- coding: utf-8 -*-
"""
Created on Thu Sep 12 14:13:52 2024

@author: moazz
"""

import os
import pandas as pd

# Define the folder paths
input_folder = "C:\PhD Project\Measurement Data\DOE-June\S1\S1-set-reset"  # Replace with the path to your CSV folder
output_file = "C:\PhD Project\Measurement Data\DOE-June\S1" # Replace with the path to your output file

# Initialize an empty DataFrame for storing the results
output_df = pd.DataFrame(columns=['Column_3_Row_1056', 'Column_3_Row_604'])

# Loop through all the CSV files in the input folder
for file_name in os.listdir(input_folder):
    if file_name.endswith('.csv'):  # Ensure the file is a CSV
        file_path = os.path.join(input_folder, file_name)
        
        # Read the CSV file into a DataFrame, ignoring row 137 (index 136) and problematic lines
        try:
            df = pd.read_csv(file_path, on_bad_lines='skip').drop(index=136, errors='ignore')
        except pd.errors.EmptyDataError:
            print(f"File {file_name} is empty. Skipping.")
            continue

        # Check if the required rows and columns exist
        if df.shape[0] > 1055 and df.shape[1] > 2:
            # Extract data from Column 3, Row 1056 (index 1055 in pandas)
            row_1056_value = df.iloc[1055, 2]
        else:
            print(f"File {file_name} does not contain enough rows or columns. Skipping.")
            continue
        
        if df.shape[0] > 603 and df.shape[1] > 2:
            # Extract data from Column 3, Row 604 (index 603 in pandas)
            row_604_value = df.iloc[603, 2]
        else:
            print(f"File {file_name} does not contain enough rows or columns. Skipping.")
            continue

        # Append the extracted values to the output DataFrame
        output_df = output_df.append({
            'Column_3_Row_1056': row_1056_value,
            'Column_3_Row_604': row_604_value
        }, ignore_index=True)

# Save the output DataFrame to a CSV file
output_df.to_csv(output_file, index=False)

print(f"Data extraction completed. Results saved to {output_file}.")
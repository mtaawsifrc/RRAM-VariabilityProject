import os
import pandas as pd

def process_csv_files(folder_path, output_csv_path):
    # Initialize lists to store the results for each file
    file_names = []
    max_subtractions = []
    corresponding_data_points = []

    # Iterate over each CSV file in the specified folder
    for filename in os.listdir(folder_path):
        if filename.endswith(".csv"):
            file_path = os.path.join(folder_path, filename)

            # Read the CSV file into a pandas DataFrame, skipping the first column and the first 253 rows
            df = pd.read_csv(file_path, usecols=[1, 2], skiprows=1050)

            # Perform the subtraction operation on the second column
            df['Subtraction'] = df.iloc[:, 1].diff()

            # Find the maximum subtraction value and its corresponding data point
            max_subtraction_row = df.loc[df['Subtraction'].idxmax()]
            max_subtraction = max_subtraction_row['Subtraction']
            corresponding_data_point = max_subtraction_row.iloc[0]

            # Store the results for each file
            file_names.append(filename)
            max_subtractions.append(max_subtraction)
            corresponding_data_points.append(corresponding_data_point)

    # Create a DataFrame with the results
    result_df = pd.DataFrame({
        'File Name': file_names,
        'Corresponding Data Point': corresponding_data_points,
        'Maximum Subtraction': max_subtractions
    })

    # Save the result to a new CSV file
    result_df.to_csv(output_csv_path, index=False)

# Specify the folder path containing the CSV files
folder_path = 'set-reset-new'

# Specify the path for the output CSV file
output_csv_path = 'set Voltage-S6-new.csv'

# Call the function to process CSV files and save the result
process_csv_files(folder_path, output_csv_path)

print(f"Result saved to {output_csv_path}")

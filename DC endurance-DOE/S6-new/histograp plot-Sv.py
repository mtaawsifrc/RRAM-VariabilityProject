
"""
Created on Sun Jun 30 12:17:28 2024

@author: moazz
"""

import matplotlib.pyplot as plt
import pandas as pd

def plot_histogram_from_csv(file_path, column_name, num_bins, output_file):
    # Read data from CSV
    data = pd.read_csv(file_path)

    # Extract the specified column
    values = data[column_name].dropna()  # Drop NaN values

    # Plot histogram
    plt.hist(values, bins=num_bins, color='blue', alpha=0.7)
    plt.xlabel('Voltage (V)')
    plt.ylabel('Frequency')
    plt.title('S6-SET Voltage')
    
    # Save the plot as a JPG file
    plt.savefig(output_file, format='jpg')
    plt.show()

# Example usage
file_path = 'Set Voltage-S6-new.csv'  # Path to your CSV file
column_name = 'Corresponding Data Point'  # Column name to plot
num_bins =300  # Number of bins
output_file = 'S4-SV-histogram-new.jpg'  # Output file name

plot_histogram_from_csv(file_path, column_name, num_bins, output_file)

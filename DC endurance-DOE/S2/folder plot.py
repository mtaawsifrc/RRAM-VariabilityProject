import os
import matplotlib.pyplot as plt
import pandas as pd

# Set the path to the folder containing CSV files
folder_path = 'Forming'
# Get a list of all CSV files in the folder
csv_files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]

# Create a figure and axis for the plot
plt.rcParams.update({'font.size': 24})
plt.figure(figsize=(14, 10))
ax = plt.subplot(1, 1, 1)

# Iterate through each CSV file and plot its data
for csv_file in csv_files:
    csv_path = os.path.join(folder_path, csv_file)
    
    # Assuming you want to skip the first 250 rows and data is in columns 2 and 3
    df = pd.read_csv(csv_path, skiprows=252, usecols=[1, 2], header=None)
    
    # Extract the file name without the extension for the legend label
    legend_label = os.path.splitext(csv_file)[0]
    
    plt.plot(df[1], df[2]*1e3, label=legend_label, marker='o', markersize=8)  # Adding label to the plot

# Add labels and legend
plt.xlabel('Voltage (V)')
plt.ylabel('Current (mA)')

#modify the x and y axis range 

#plt.ylim(-2.5, 1.5)
#plt.xlim(-1, 1)    

# Customize the legend
#legend = plt.legend(fontsize=16, loc='upper left')  # Change font size and location


output_image_path = 'S2-form.jpg'
plt.savefig(output_image_path, format='jpg', bbox_inches='tight')  # Use bbox_inches to avoid cropping legend
# Show the plot
plt.show()

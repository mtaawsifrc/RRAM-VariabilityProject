import os
import matplotlib.pyplot as plt
import pandas as pd
import matplotlib.cm as cm

# Set the path to the folder containing CSV files
folder_path = 'c3-1-4um-06'
# Get a list of all CSV files in the folder
csv_files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]

# Define a base color and use a colormap to generate shades
base_color = cm.Blues  # You can change this to other colormaps like cm.Reds, cm.Greens, etc.
num_files = len(csv_files)

# Create a figure and axis for the plot
plt.figure(figsize=(10, 6))
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = "Times New Roman"
plt.rcParams["font.size"] = 8
plt.rcParams["mathtext.fontset"] = "dejavuserif"
plt.rcParams['xtick.direction'] = 'in'
plt.rcParams['ytick.direction'] = 'in'
plt.rcParams['xtick.major.size'] = 4
plt.rcParams['ytick.major.size'] = 4
plt.rcParams['xtick.major.width'] = 1.0
plt.rcParams['ytick.major.width'] = 1.0
plt.rcParams['axes.linewidth'] = 1
plt.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(figsize=(3.3, 2.5))
ax.tick_params(bottom=True,  left=True, )
ax.tick_params(labelbottom=True, labelleft=True)

# Iterate through each CSV file and plot its data
for i, csv_file in enumerate(csv_files):
    csv_path = os.path.join(folder_path, csv_file)
    
    # Read the data for the first range (rows 146 to 347)
    df1 = pd.read_csv(csv_path, skiprows=145, nrows=202, usecols=[1, 2], header=None)
    # Read the data for the second range (rows 1052 to 1453)
    df2 = pd.read_csv(csv_path, skiprows=1051, nrows=402, usecols=[1, 2], header=None)
    
    # Extract the file name without the extension for the legend label
    legend_label = os.path.splitext(csv_file)[0]
    
    # Calculate the color and transparency based on the file order
    color1 = base_color(i / num_files)  # Color for the first range
    color2 = base_color((i + 0.5) / num_files)  # Slightly different color for the second range
    alpha_value = 0.8 - (i / (2 * num_files))  # Gradually decreasing transparency
    
    # Plot the data for the first range
    plt.plot(df1[1], df1[2]*1e3, label=f'{legend_label} (146-347)', color=color1, alpha=alpha_value, marker='o', markersize=1)
    # Plot the data for the second range
    plt.plot(df2[1], df2[2]*1e3, label=f'{legend_label} (1052-1453)', color=color2, alpha=alpha_value, marker='x', markersize=1)

# Add labels and legend
plt.xlabel('Voltage (V)')
plt.ylabel('Current (mA)')

# Customize the legend
#plt.legend(fontsize=6, loc='upper left')  # Adjust font size and location as needed

output_image_path = 'Forming.jpg'
plt.savefig(output_image_path, format='jpg', dpi=600, bbox_inches='tight')  # Use bbox_inches to avoid cropping legend

# Show the plot
plt.show()

# -*- coding: utf-8 -*-
"""
Created on Sun Dec 22 14:48:05 2024

@author: moazz
"""

import os
import matplotlib.pyplot as plt
import pandas as pd

# Set the paths to the folders containing CSV files
folder_path1 = 'Forming-Figure'
folder_path2 = 'edn2'
folder_path3 = 'edn2'
folder_path4 = '1st cycle'
folder_path5 = r'1st reset'
# Get a list of all CSV files in the folders
csv_files1 = [f for f in os.listdir(folder_path1) if f.endswith('.csv')]
csv_files2 = [f for f in os.listdir(folder_path2) if f.endswith('.csv')]
csv_files3 = [f for f in os.listdir(folder_path3) if f.endswith('.csv')]
csv_files4 = [f for f in os.listdir(folder_path4) if f.endswith('.csv')]
csv_files5 = [f for f in os.listdir(folder_path5) if f.endswith('.csv')]
# Set plot appearance properties
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = "Arial"
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
ax.tick_params(
    bottom=True, top=True,
    left=True, right=True)
ax.tick_params(
    labelbottom=True, 
    labelleft=True)

# Add minor ticks
ax.minorticks_on()
ax.tick_params(which='minor', length=2, width=0.75)

# Set y-axis to logarithmic scale
ax.set_yscale('log')

# Plot data from the first folder (Forming-Figure) - Red
for csv_file in csv_files1:
    csv_path = os.path.join(folder_path1, csv_file)
    df = pd.read_csv(csv_path, skiprows=253, usecols=[1, 2], header=None)
    plt.plot(df[1], df[2], label='Electroforming', marker='o', markersize=0.5, linewidth=1, color='red')

# Plot data from the second folder (edn2) - Gray
for csv_file in csv_files2:
    csv_path = os.path.join(folder_path2, csv_file)
    df = pd.read_csv(csv_path, skiprows=145, nrows=202, usecols=[1, 2], header=None)
    plt.plot(df[1], df[2]*-1, marker='x', markersize=0.2, linewidth=0.2, color='gray')

# Plot data from the third folder (edn2) - Gray
for csv_file in csv_files3:
    csv_path = os.path.join(folder_path3, csv_file)
    df = pd.read_csv(csv_path, skiprows=1051, nrows=403, usecols=[1, 2], header=None)
    plt.plot(df[1], df[2], marker='s', markersize=0.2, linewidth=0.2, color='gray')

# Plot data from the fourth folder (1st cycle) - Blue
for csv_file in csv_files4:
    csv_path = os.path.join(folder_path4, csv_file)
    df = pd.read_csv(csv_path, skiprows=1051, nrows=604, usecols=[1, 2], header=None)
    plt.plot(df[1], df[2], label='Set-Reset', marker='s', markersize=0.5, linewidth=0.5, color='blue')

# Plot data from thefolder 1st reset
for csv_file in csv_files5:
    csv_path = os.path.join(folder_path5, csv_file)
    df = pd.read_csv(csv_path, skiprows=252, usecols=[1, 2], header=None)
    plt.plot(df[1], df[2]*-1, label='1st Reset', marker='o', markersize=0.5, linewidth=1, color='Orange')

# Add labels and legend
plt.ylabel('Current (A)')
plt.xlabel('Voltage (V)')

# Modify the x and y axis range
plt.ylim(5e-9, 1.5e-2)
plt.xlim(-4, 6, 1)

# Customize the legend
legend = plt.legend(fontsize=8, loc='lower right')
legend.get_frame().set_visible(False)  # Remove legend frame

# Add a text annotation in the middle of the plot
plt.text(3.8, 1e-5, "Oxygen poor sample", fontsize=8, ha='center', va='center')
plt.text(3.8, 4e-6, "(O:20%, P:250W)", fontsize=8, ha='center', va='center')

plt.text(1.7, 5e-4, "SET", fontsize=8, ha='center', va='center', color='blue')
plt.text(-0.6, 6e-3, "RESET", fontsize=8, ha='center', va='center', color='blue')
# Save and show the plot
output_image_path = 'I-V2.jpg'
plt.savefig(output_image_path, format='jpg', dpi=1200, bbox_inches='tight')
plt.show()

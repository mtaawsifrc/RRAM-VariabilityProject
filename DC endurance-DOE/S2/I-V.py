# -*- coding: utf-8 -*-
"""
Created on Sun Dec 22 14:06:55 2024

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

# Get a list of all CSV files in the folders
csv_files1 = [f for f in os.listdir(folder_path1) if f.endswith('.csv')]
csv_files2 = [f for f in os.listdir(folder_path2) if f.endswith('.csv')]
csv_files3 = [f for f in os.listdir(folder_path3) if f.endswith('.csv')]
csv_files4 = [f for f in os.listdir(folder_path4) if f.endswith('.csv')]

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

# Plot data from the first folder (Forming-Figure) - Red
for csv_file in csv_files1:
    csv_path = os.path.join(folder_path1, csv_file)
    df = pd.read_csv(csv_path, skiprows=253, usecols=[1, 2], header=None)
    legend_label = os.path.splitext(csv_file)[0] + ' (Forming-Figure)'
    plt.plot(df[1], df[2]*1e3, label='Electroforming', marker='o', markersize=0.5, linewidth=1, color='red')

# # Plot data from the second folder (edn2) - Gray
for csv_file in csv_files2:
    csv_path = os.path.join(folder_path2, csv_file)
    df = pd.read_csv(csv_path, skiprows=145, nrows=202, usecols=[1, 2], header=None)
    legend_label = os.path.splitext(csv_file)[0] + ' (edn2)'
    plt.plot(df[1], df[2]*1e3,  marker='x', markersize=0.2, linewidth=0.2, color='gray')

# # Plot data from the third folder (edn2) - Gray
for csv_file in csv_files3:
    csv_path = os.path.join(folder_path3, csv_file)
    df = pd.read_csv(csv_path, skiprows=1051, nrows=403, usecols=[1, 2], header=None)
    legend_label = os.path.splitext(csv_file)[0] + ' (edn2)'
    plt.plot(df[1], df[2]*1e3, marker='s', markersize=0.2, linewidth=0.2, color='gray')

# Plot data from the fourth folder (1st cycle) - Blue
for csv_file in csv_files4:
    csv_path = os.path.join(folder_path4, csv_file)
    df = pd.read_csv(csv_path, skiprows=1051, nrows=604, usecols=[1, 2], header=None)
    legend_label = os.path.splitext(csv_file)[0] + ' (1st cycle)'
    plt.plot(df[1], df[2]*1e3, label='Set-Reset', marker='s', markersize=0.5, linewidth=0.5, color='blue')

# Add labels and legend
plt.ylabel('Current (mA)')
plt.xlabel('Voltge (V)')

# Modify the x and y axis range
plt.ylim(-5, 5, 1)
plt.xlim(-3, 5, 1)

# Customize the legend
legend = plt.legend(fontsize=8, loc='lower right')

# Save and show the plot
output_image_path = 'I-V-linear1.jpg'
plt.savefig(output_image_path, format='jpg', dpi=600, bbox_inches='tight')
plt.show()

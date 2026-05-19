# -*- coding: utf-8 -*-
"""
Created on Mon Oct 28 16:41:41 2024

@author: moazz
"""

import os
import csv
import re
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Read the CSV files
df2 = pd.read_csv('S3-i-v.csv')

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
ax.tick_params(bottom=True, left=True)
ax.tick_params(labelbottom=True, labelleft=True)

# Plot with logarithmic y scale and absolute values for currents
ax.set_yscale('log')
ax.plot(df2[' V1-form'], np.abs(df2['i1-form']), '-ok', label='Electroforming', color='blue', markersize=1)
ax.plot(df2['V1-set'], np.abs(df2['i1-set']), '-ok', label='Set-Reset', color='red', markersize=1)

ax.legend(loc="lower right", ncol=3, fontsize=7)

# Add x and y labels
ax.set_xlabel('Voltage (V)')
ax.set_ylabel('Current (A)')

# Adjust x and y limits
plt.xticks(np.arange(-3, 7, 1))
ax.set_xlim(-3, 7)
#plt.yticks([1, 10, 100, 1000, 10000])  # Example y-ticks for log scale

plt.savefig('I-V-logscale.jpeg', dpi=600, facecolor='w', edgecolor='w', transparent=False,
            orientation='portrait', bbox_inches='tight')

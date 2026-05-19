import os
import csv
import re
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
# import colour
from matplotlib.ticker import ScalarFormatter

custom_colors = ['#FF5733', '#33FF57', '#5733FF', '#FFFF33', '#33FFFF',
                 '#FF33FF', '#FF5733', '#33FF57', '#5733FF', '#FFFF33']

# Read the CSV files
hrs2 = pd.read_csv('S2-Hrs.csv')
lrs2 = pd.read_csv('S2-Lrs.csv')
# hrs3 = pd.read_csv('3-Hrs.csv')
# lrs3 = pd.read_csv('3-Lrs.csv')
# hrs4 = pd.read_csv('4-Hrs.csv')
# lrs4 = pd.read_csv('4-Lrs.csv')
# hrs5 = pd.read_csv('5-Hrs.csv')
# lrs5 = pd.read_csv('5-Lrs.csv')
# hrs7 = pd.read_csv('7-Hrs.csv')
# lrs7 = pd.read_csv('7-Lrs.csv')
# hrs8 = pd.read_csv('8-Hrs.csv')
# lrs8 = pd.read_csv('8-Lrs.csv')
# hrs9 = pd.read_csv('9-Hrs.csv')
# lrs9 = pd.read_csv('9-Lrs.csv')
# hrs10 = pd.read_csv('10-Hrs.csv')
# lrs10 = pd.read_csv('10-Lrs.csv')
# hrs11 = pd.read_csv('11-Hrs.csv')
# lrs11 = pd.read_csv('11-Lrs.csv')
# hrs13 = pd.read_csv('13-Hrs.csv')
# lrs13 = pd.read_csv('13-Lrs.csv')

plt.rcParams['axes.prop_cycle'] = plt.cycler(color=custom_colors)

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


ax.plot(hrs2['Data Points'], hrs2['CDF'], 'ok', label='S2', color='blue', lw=0.5, markersize=1)
ax.plot(lrs2['Data Points'], lrs2['CDF'], 's',  color='blue', lw=0.5, markersize=1)

# ax.plot(hrs3['Data Points'], hrs3['CDF'], 'ok', label='Device 2', color='#B9D3EE', lw=0.5, markersize=1)
# ax.plot(lrs3['Data Points'], lrs3['CDF'], 's', color='#B9D3EE', lw=0.5, markersize=1)

# ax.plot(hrs4['Data Points'], hrs4['CDF'], 'ok', label='Device 3', color='#7EC0EE', lw=0.5, markersize=1)
# ax.plot(lrs4['Data Points'], lrs4['CDF'], 's',  color='#7EC0EE', lw=0.5, markersize=1)

# ax.plot(hrs5['Data Points'], hrs5['CDF'], 'ok', label='Device 4', color='#7171C6', lw=0.5, markersize=1)
# ax.plot(lrs5['Data Points'], lrs5['CDF'], 's',  color='#7171C6', lw=0.5, markersize=1)

# ax.plot(hrs7['Data Points'], hrs7['CDF'], 'ok', label='Device 5', color='#27408B', lw=0.5, markersize=1)
# ax.plot(lrs7['Data Points'], lrs7['CDF'], 's', color='#27408B', lw=0.5, markersize=1)

# ax.plot(hrs8['Data Points'], hrs8['CDF'], 'ok', label='Device 6', color='#4876FF', lw=0.5, markersize=1)
# ax.plot(lrs8['Data Points'], lrs8['CDF'], 's',  color='#4876FF', lw=0.5, markersize=1)

# ax.plot(hrs9['Data Points'], hrs9['CDF'], 'ok', label='Device 7', color='#5733FF', lw=0.5, markersize=1)
# ax.plot(lrs9['Data Points'], lrs9['CDF'], 's',  color='#5733FF', lw=0.5, markersize=1)

# ax.plot(hrs10['Data Points'], hrs10['CDF'], 'ok', label='Device 8', color='#33A1C9', lw=0.5, markersize=1)
# ax.plot(lrs10['Data Points'], lrs10['CDF'], 's',  color='#33A1C9', lw=0.5, markersize=1)

# ax.plot(hrs11['Data Points'], hrs11['CDF'], 'ok', label='Device 9', color='#191970', lw=0.5, markersize=1)
# ax.plot(lrs11['Data Points'], lrs11['CDF'], 's', color='#191970', lw=0.5, markersize=1)

# ax.plot(hrs13['Data Points'], hrs13['CDF'], 'ok', label='Device 10', color='red', lw=0.5, markersize=1)
# ax.plot(lrs13['Data Points'], lrs13['CDF'], 's', color='red', lw=0.5, markersize=1)

ax.legend(loc="upper left", ncol=1, fontsize=5)

plt.xscale('log')
# Add x and y labels
ax.set_xlabel('Current (A)')
ax.set_ylabel('Cumulative Probability')

# Set custom tick positions and labels for the x-axis
xtick_positions = [1e-6, 1e-5, 1e-4, 1e-3]
xtick_labels = ['1e-6', '1e-5', '1e-4', '1e-3']

plt.xticks(xtick_positions, xtick_labels)


# Change x-axis tick numbers to power style (scientific notation)
# ax.xaxis.set_major_formatter(ScalarFormatter(useMathText=True))
# ax.xaxis.get_major_formatter().set_powerlimits((0, 0))
# ax.xaxis.offsetText.set_visible(False)

ax.set_xlim(5e-7, 1e-3)
ax.set_ylim(-0.1, 1.1)
plt.yticks(np.arange(0, 1.1, 0.1))

plt.savefig('CDF 22323.jpeg', dpi=600, facecolor='w', edgecolor='w', transparent=False,
            orientation='portrait', bbox_inches='tight')

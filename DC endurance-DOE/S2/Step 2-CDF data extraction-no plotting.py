# -*- coding: utf-8 -*-
"""
Created on Sat Jul 29 22:48:10 2023

@author: moazz
"""

import os
import csv
import re
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np


def plot_cdf(data, xlabel=None, ylabel='CDF', title=None, output_file=None):
    sorted_data = np.sort(data)
    n = len(data)
    cdf = np.arange(1, n + 1) / n

    plt.plot(sorted_data, cdf, marker='.', linestyle='none')
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True)

    if output_file:
        # Save the sorted data and CDF values to a CSV file
        output_data = np.column_stack((sorted_data, cdf))
        np.savetxt(output_file, output_data, delimiter=',', header=f'{xlabel},{ylabel}', comments='')

    plt.show()
df2 = pd.read_csv('S2-extracted_data.csv')
# data= df2['a']
#data = np.random.normal(loc=0, scale=1, size=1000)  # Example: 1000 random data points from a normal distribution
output_file = 'S2-Hrs.csv'

plot_cdf(df2['HRS'], xlabel='Data Points', ylabel='CDF', title='Cumulative Density Function', output_file=output_file)
# plot_cdf(df2['c'], xlabel='Data Points', ylabel='CDF', title='Cumulative Density Function', output_file=output_file)

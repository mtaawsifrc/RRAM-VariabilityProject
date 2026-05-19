import os
import pandas as pd
import matplotlib.pyplot as plt
import re

def plot_data_from_folder(folder_path):
    # Get list of CSV files in the folder
    csv_files = [file for file in os.listdir(folder_path) if file.endswith('.csv')]
    
    # Initialize an empty DataFrame to store all data
    all_data = pd.DataFrame()

    # Read data from each CSV file and append to all_data DataFrame
    for file in csv_files:
        file_path = os.path.join(folder_path, file)
        df = pd.read_csv(file_path)
        df['current'] = pd.to_numeric(df['current'], errors='coerce')  # Convert 'current' to numeric
        df['time'] = pd.to_numeric(df['time'], errors='coerce')  # Convert 'time' to numeric
        all_data = all_data.append(df[['time', 'current']], ignore_index=True)
    
    # Plotting
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
    
    # Dictionary to map file names to colors
    color_map = {'50us': 'red', '200us': 'green', '400us': 'blue'}
    
    for file in csv_files:
        # Extract color group from file name
        color_group = None
        for term, col in color_map.items():
            if term in file:
                color_group = col
                break
        
        # Extract index number from file name
        match = re.search(r'\((\d+)\)', file)
        if match:
            index_number = int(match.group(1))
            # Calculate intensity based on index number (1 to 10)
            intensity = index_number / 10  # Map index to intensity in range [0, 1]
            # Adjust color intensity
            color = tuple((1 - intensity) * c for c in plt.cm.colors.to_rgb(color_group))
        else:
            color = color_group  # Default to color group
        
        file_path = os.path.join(folder_path, file)
        df = pd.read_csv(file_path)
        plt.plot(df['time'], df['current']*-1e5, linewidth=0.5, color=color, alpha=0.5, label=f'cycle {file}')
        
    plt.xlabel('Time (s)')
    plt.ylabel('Current (uA)')
    plt.title('Long term Potentiation')
    plt.legend(loc="upper right", ncol=6, fontsize= 3)
    plt.savefig('ltd.jpeg', dpi=600, facecolor='w', edgecolor='w', transparent=False,
                orientation='portrait', bbox_inches='tight')
    plt.show()

# Example usage
folder_path = ''
plot_data_from_folder(folder_path)

# -*- coding: utf-8 -*-
"""
Created on Tue Oct  3 15:56:50 2023

@author: papin

This script performs a network cross-correlation analysis on seismic data with
already known events as templates, in order to detect new events.
Functions are from autocorrelation and cross-correlation tools modules.

Description (not specifically in order):
1. Creates an info.txt file with relevant information about the data.
2. Loads seismic data from specified stations and channels for a given date.
3. Preprocesses the data by trimming, interpolating, detrending, and filtering.
4. Plots the full streams of seismic data.
5. Defines templates for cross-correlation analysis by using already known events.
6. Plots the station locations as well as the templates locations (optional).
7. Computes cross-correlation coefficients between each station's data and the template.
8. Detects significant correlations based on a specified threshold.
9. Generates and saves plots for cross-correlation analysis with detected events.
10. Outputs the new detected events times to a text file.
11. Stack and plot all detected events of each template.

Note: This code is made for cross-correlation for several days of continuous 
data. If you want a day, you still have to enter 2 dates of interests.

As of 12/13/23.
"""

import os
import time
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from obspy import UTCDateTime
from obspy.core import Stream
import autocorr_tools
import crosscorr_tools

import matplotlib
matplotlib.use('Agg')

# Define the base directory
base_dir = "C:/Users/papin/Desktop/phd/"

# Plot station locations
locfile = pd.read_csv(os.path.join(base_dir, 'stations.csv'))
locs = locfile[['Name', 'Longitude', 'Latitude','Network']].values

# Start timer
startscript = time.time()

# Define the network configurations (CN & PB)
# NLLB removed, careful for some of the B stations (B010 + B926)
network_config = {
    'CN1': {
        'stations': ['LZB', 'PGC', 'SNB'],
        'channels': ['BHN', 'BHE', 'BHZ'],
        'filename_pattern': '{date}.CN.{station}..{channel}.mseed'
    },
    'CN2': {
        'stations': ['YOUB', 'PFB'],
        'channels': ['HHN', 'HHE', 'HHZ'],
        'filename_pattern': '{date}.CN.{station}..{channel}.mseed'
    },
    'PB': {
        'stations': ['B001', 'B009', 'B011'],
        'channels': ['EH1', 'EH2', 'EHZ'],
        'filename_pattern': '{station}.PB.{year}.{julian_day}'
    }
}

# Days of data
date_of_interests = ["20100516","20100517","20100518","20100519","20100520"]
startdate=datetime.strptime(date_of_interests[0], "%Y%m%d")
enddate=startdate+timedelta(days=len(date_of_interests) - 1)

# Frequency range, sampling_rate, and time window
freqmin = 2.0
freqmax = 8.0
sampling_rate = 40.0
win_size = 30

# Get the streams and preprocess ###actualize the get_traces fct
st=Stream()
for date_of_interest in date_of_interests:
    st += Stream(traces=crosscorr_tools.get_traces(network_config, date_of_interest, base_dir))
st._trim_common_channels()
st._cleanup()
st = crosscorr_tools.process_data(st, sampling_rate, freqmin, freqmax, startdate, enddate)

# List of stations/channels to analyze
stas = [network_config[key]['stations'] for key in network_config]
channels = [network_config[key]['channels'] for key in network_config]

# To create beforehand
folder = f"{date_of_interest} {len(date_of_interests)}days" #Last day of the series

# Plot all the streams and get all the combination of sta/cha
data_plot_filename = os.path.join(
    base_dir,
    f'plots/{folder}/data_plot_{date_of_interest}.png'
)
pairs = crosscorr_tools.plot_data(st, stas, channels, data_plot_filename)
# If no plot :
pairs = [f"{sta}..{cha}" for sta_list, cha_list in zip(stas, channels) 
          for sta in sta_list for cha in cha_list]

# Load LFE data on Tim's catalog
templates=pd.read_csv('./EQloc_001_0.1_3_S.txt_withdates', index_col=0)
templates=templates[(templates['residual']<0.5)]
templates['datetime']=pd.to_datetime(templates['OT'])
templates = templates[(templates['datetime'] >= st[0].stats.starttime.datetime)
                    & (templates['datetime'] < st[0].stats.endtime.datetime)
                    & (templates['residual'] < 0.1)]
templates = templates.drop(columns=['dates', 'N'])
templates.reset_index(inplace=True, drop=True)
templates.index.name = 'Index'

# Plot locations of events and stations
events = templates[['lon', 'lat', 'depth', 'datetime']]
# crosscorr_tools.plot_locations(locs, base_dir, events=events)

# Collect information
info_lines = []  # Store lines of information
num_detections = 0

# Generate the output files paths
info_file_path = os.path.join(base_dir, 'plots', f"{folder}", "info.txt")
output_file_path = os.path.join(base_dir, 'plots', f"{folder}", 'output.txt')

# You can choose which templates
templ_no=109
templates=templates[templ_no:templ_no+1]
# templates=templates.iloc[::5]

# Iterate over all templates
for idx, template_stats in templates.iterrows():
    # Initialization
    template=[]
    all_template=[]
    templ_idx=idx
    crosscorr_combination = f'templ{idx}'
    xcorr_full=np.zeros(int(st[0].stats.npts-(win_size*sampling_rate)))

    # Iterate over all stations and channels combination
    for tr in st:
        # Template data
        start_templ = UTCDateTime(template_stats['datetime'] + timedelta(seconds=10))
        end_templ = start_templ + timedelta(seconds=win_size)
        if end_templ.day != enddate.day:
            print('Last template has an ending time on a wrong day: not processed.')
            break
        template = tr.copy().trim(starttime=start_templ, endtime=end_templ)
        all_template.append(template)
        xcorr_template = autocorr_tools.correlate_template(
            tr.data, template.data,
            mode='valid', normalize='full', demean=True, method='auto'
        )
        # process_data gives a difference of 1 sample between some streams so 
        # it cuts the streams at the same length 
        if len(xcorr_template)<len(xcorr_full):
            xcorr_full=xcorr_full[:len(xcorr_template)]
        xcorr_full+=xcorr_template

    # Network cross-correlation
    xcorrmean=xcorr_full/len(st)

    # If it goes over the next day, template not defined and end of the run
    if template==[]:
        break
    
    # Plot template time window on each sta..cha combination
    template_plot_filename = os.path.join(
        base_dir,
        f'plots/{folder}/{crosscorr_combination}_template_'
        f'{date_of_interest}.png'
    )
    crosscorr_tools.plot_template(all_template, pairs, templ_idx, template_plot_filename)

    # Find indices where the cross-correlation values are above the threshold
    mad = np.median(np.abs(xcorrmean - np.median(xcorrmean)))
    thresh = 8 * mad
    aboves = np.where(xcorrmean > thresh)

    # Template does match at least once (cc value of 1)
    if aboves[0].size > 0:
        # Calculate the window length for clustering
        windowlen = template.stats.npts
        # Indices where the cross-correlation values are above the threshold
        inds = aboves[0]
        # Cluster the detected events
        clusters = autocorr_tools.clusterdects(inds, windowlen)
        # Cull detections within clusters
        newdect = autocorr_tools.culldects(inds, clusters, xcorrmean)
        # Find the index of the maximum value in newdect
        max_index = np.argmax(xcorrmean[newdect])

        # Creation of the cross-correlation plot only if new events detected
        if newdect.size > 1:
            # Plot of the crosscorr function
            crosscorr_plot_filename = os.path.join(
                base_dir,
                f'plots/{folder}/{crosscorr_combination}_crosscorr_'
                f'{date_of_interest}.png'
            )
            crosscorr_tools.plot_crosscorr(tr, xcorrmean, thresh, newdect,
                                           max_index, crosscorr_combination,
                                           date_of_interest, crosscorr_plot_filename)

            # Plot of the stacked traces
            stack_plot_filename = os.path.join(
                base_dir,
                f'plots/{folder}/{crosscorr_combination}_stack_'
                f'{date_of_interest}.png'
            )
            crosscorr_tools.plot_stacks(st, template, newdect, pairs,
                                        templ_idx, stack_plot_filename)

            ## Writing in output.txt
            # Create UTCDateTime objects from the newevent values
            newevent = np.delete(newdect, max_index)*tr.stats.delta
            # FIXME: Doesn't take the primary event in the template in utc_times
            # which is the time of every detections for 1 template
            utc_times = [tr.stats.starttime.datetime +
                         timedelta(seconds=event) for event in newevent]
            # Keep track of combination with the most detected events
            if newevent.size>=100:
                info_lines.append(f"{crosscorr_combination}")
            num_detections+=newevent.size
            # Save the cross-correlation values for each newevent
            mask = xcorrmean[newdect] != (xcorrmean[newdect])[max_index]
            cc_values = xcorrmean[newdect][mask]
            #  Write the newevent and additional columns to the output file
            with open(output_file_path, "a", encoding=("utf-8")) as output_file:
                if os.stat(output_file_path).st_size == 0:
                    output_file.write("starttime,templ,crosscorr value\n")
                for i, utc_time in enumerate(utc_times):
                    output_file.write(
                        f"{UTCDateTime(utc_time).strftime('%Y-%m-%dT%H:%M:%S.%f')},"
                        f"{templ_idx},{cc_values[i]:.4f}\n"
                    )

    # Follow the advancement
    print(f"Processed template {templ_idx + 1}/{len(templates)}")

# Calculate and print script execution time
end_script = time.time()
script_execution_time = end_script - startscript
print(f"Script execution time: {script_execution_time:.2f} seconds")
# Get the list of stations and channels used
pairs_used = ", ".join(pairs)
# Write the info of the run in the output file
with open(info_file_path, 'w', encoding='utf-8') as file:
    file.write(f"Date Range: {startdate} - {enddate}\n\n")
    file.write(f"Stations and Channels Used: {pairs_used}\n\n")
    file.write(f"Frequency range: {freqmin}-{freqmax} Hz\n")
    file.write(f"Sampling rate: {sampling_rate} Hz\n\n")
    file.write(f"Total of detections: {num_detections} \n")
    file.write("More than 100 detections:\n")
    file.write("\n".join(info_lines) + '\n\n')
    file.write("Templates info:\n")
    file.write(templates.to_string() + '\n')

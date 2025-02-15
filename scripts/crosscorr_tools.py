# -*- coding: utf-8 -*-
"""
Created on Mon Oct 16 14:48:37 2023

This module provides functions for seismic data processing, visualization, and analysis.
The functions cover loading and preprocessing data, plotting seismic traces, creating
summed traces around detected events, and more.

Functions:
- build_file_path: Gives file names for plots.
- get_traces: Load seismic data for specified stations, channels, and date.
- process_data: Preprocess seismic data, including interpolation, trimming,
  detrending, and filtering.
- process_streams: Filter the seismic traces for the first templates.
- plot_data: Plot seismic station data for a specific date, including normalized
  traces with an offset.
- plot_crosscorr: Plot the resulted cross-correlation function for 1 template
  on the network.
- plot_template: Plot the template for each station/channel combination.
- plot_stacks: Plot the combined traces for all detections of a template for each
  station/channel combination.
- plot_locations: Create a plot of station locations and template events on a map.

@author: papin

As of 01/11/24.
"""

import os
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
from obspy import UTCDateTime
from obspy.core import read, Stream

# ========== Files Management ==========

def build_file_path(base_dir, folder, name, prefix, lastday):
    """
    Build a file path for saving plots (related to plot_template, plot_stacks,
    plot_crosscorr in crosscorr_tools module).

    Parameters:
        base_dir (str): The base directory where the file will be saved.
        folder (str): The subfolder within the base directory for organization.
        name (str): The base name of the file (usually number of the template).
        prefix (str): A prefix to be included in the file name.
        lastday (str): The last day identifier to be included in the file name.
    """
    return os.path.join(base_dir, f'plots/{folder}/{name}_{prefix}_{lastday}.png')

# ========== Data Loading & Process Streams ==========

def get_traces(network_config, date_of_interests, base_dir):
    """
    Retrieve seismic traces for specified stations and channels on a given dates.

    Parameters:
        network_config (dict): A dictionary containing configuration details for each network.
        date_of_interests (str): The dates in the format 'YYYYMMDD'
        base_dir (str): The base directory for file paths.

    Returns:
        st (obspy.core.Stream): Seismic data streams.
    """
    path = os.path.join(base_dir, 'data', 'seed')
    st = Stream()

    # Read all the files corresping to the stations defined in network_config
    for date in date_of_interests:
        for network, config in network_config.items():
            stations = config['stations']
            channels = config['channels']
            filename_pattern = config['filename_pattern']
            for sta in stations:
                try:
                    if network == 'PB':
                        dt = datetime.strptime(date, '%Y%m%d')
                        julian_day = (dt - datetime(dt.year, 1, 1)).days + 1
                        file = os.path.join(path, filename_pattern.format(station=sta, year=dt.year, julian_day=julian_day))
                        st += read(file)[:3]
                    else:
                        for cha in channels:
                            file = os.path.join(path, filename_pattern.format(date=date, station=sta, channel=cha))
                            st += read(file)[0]
                            # print(st.__str__(extended=True))
                except FileNotFoundError:
                    print(f"File not found for {network} network, station {sta}, date {date}.")

    # Merge all data by stations and channels
    st.merge(method=1,fill_value='interpolate',interpolation_samples=-1)
    st._cleanup()

    return st

def process_data(st, sampling_rate, freqmin, freqmax):
    """
    Preprocess seismic data.

    Parameters:
        st (obspy.core.Stream): Seismic data streams.
        sampling_rate (float): Sampling rate for interpolation.
        freqmin (float): Minimum frequency for bandpass filtering.
        freqmax (float): Maximum frequency for bandpass filtering.

    Returns:
        st (obspy.core.Stream): Seismic data streams.
    """
    # Initialize start and end with values that will be updated
    starttime = UTCDateTime(st[0].stats.starttime)
    endtime = UTCDateTime(st[0].stats.endtime)

    # Preprocessing: Interpolation, trimming, detrending, and filtering
    for tr in st:
        tr.trim(starttime=starttime, endtime=endtime, pad=1,
                fill_value=0, nearest_sample=False)

        if tr.stats.sampling_rate != 100.0:
            tr.interpolate(sampling_rate=100.0, starttime=starttime, endtime=endtime)
        tr.filter("bandpass", freqmin=freqmin, freqmax=freqmax)
        tr.interpolate(sampling_rate=sampling_rate)

    return st

# =============================================================================
#
# def process_streams(st, template_stats, A):
#     """
#     Process seismic traces and create a new Stream and a list of station-channel pairs.
#
#     Parameters:
#         st (obspy.core.Stream): Seismic data streams.
#         template_stats (dict): Metadata template information.
#         A (dict): Dictionary containing additional information based on the template.
#
#     Returns:
#         st2 (obspy.core.Stream): Filtered seismic data streams based on the template.
#         pairs2 (list): List of pairs corresponding to each trace in st2.
#     """
#     starttime = str(template_stats['starttime'])
#
#     # Extract information from the template
#     templ_info = A[starttime]
#     stas = templ_info['sta']
#
#     # Filter streams based on station codes
#     st2 = Stream()
#     for tr in st:
#         # Extract station code from trace id
#         station_code = tr.stats.network + '.' + tr.stats.station
#
#         # Check if the station code is in the list of desired stations
#         if station_code in stas:
#             st2 += tr
#
#     # Create a list of station-channel pairs for st2
#     pairs2 = [f"{tr.stats.station}.{tr.stats.channel}" for tr in st2]
#
#     return st2, pairs2
# =============================================================================

# ========== All Types of Plots ==========

def plot_data(st, pairs, data_plot_filename):
    """
    Plot seismic station data for a specific date. A figure for each
    station. Note that the way the function was made is for a station with its 
    3 channels; if one is removed you'll have an error.

    Parameters:
        st (obspy.core.Stream): Seismic data streams.
        stas (list of lists): List of lists of station names.
        channels (list): List of channel names.
        data_plot_filename (str): Filename for saving the plot.

    Returns:
        None
    """
    cpt=0
    for i in range(0, len(st), 3):
        plt.figure(figsize=(12, 6))
        nb = 1  # Distance between plots
        offset = len(st[i:i+3]) * nb
        for tr in st[i:i+3]:
            pair=pairs[cpt]
            norm = np.max(np.abs(tr.data))
            plt.plot(tr.times(), tr.data / norm + offset, label=f'{pair}')
            offset -= nb
            cpt+=1
        plt.xlabel('Time (s)', fontsize=14)
        plt.ylabel('Normalized Data + Offset', fontsize=14)
        plt.title(f'Data from {tr.stats.starttime.date} to {tr.stats.endtime.date}', fontsize=16)
        plt.yticks(np.arange(len(st[i:i+3])) * nb+nb, pairs[cpt-3:cpt][::-1], fontsize=12)
        plt.grid(True)
        plt.xlim(0, max(tr.times()))
        plt.ylim(0, len(st[i:i+3]) * nb + nb)
        plt.tight_layout()
        plt.savefig(f"{data_plot_filename}_{tr.stats.station}.png")
        plt.show()

def plot_crosscorr(st, xcorrmean, thresh, newdect, templ_idx,
                   crosscorr_plot_filename, cpt):
    """
    Plots cross-correlation data and saves the plot to a file.

    Parameters:
        st (obspy.core.Stream): Seismic data streams.
        xcorrmean (numpy.ndarray): The cross-correlation mean values.
        thresh (float): Threshold for the new detections.
        newdect (numpy.ndarray): Indices of the detected events.
        templ_idx (int): Index of the template.
        crosscorr_plot_filename (str): Path to save the plot.
        cpt (int): Number of the iteration for the title.

    Returns:
        None
    """
    tr=st[0]
    stream_duration = tr.stats.endtime - tr.stats.starttime
    _, ax = plt.subplots(figsize=(10, 4))

    ax.plot(tr.stats.delta * np.arange(len(xcorrmean)), xcorrmean)
    ax.axhline(thresh, color='red')
    ax.plot(newdect * tr.stats.delta, xcorrmean[newdect], 'kx')
    # ax.plot((newdect * tr.stats.delta)[max_index],
    #         (xcorrmean[newdect])[max_index], 'gx', markersize=10, linewidth=10)
    # ax.text(60, 1.1 * thresh, '8*MAD', fontsize=14, color='red')
    ax.set_xlabel('Time (s)', fontsize=14)
    ax.set_ylabel('Correlation Coefficient', fontsize=14)
    ax.set_xlim(0, stream_duration)
    # ax.set_xlim(10000, 12000)
    # ax.set_ylim(0, 0.6)
    ax.set_title(f'Cross-correlation Function for Template {templ_idx} - Iteration {cpt}', fontsize=16)
    plt.gcf().subplots_adjust(bottom=0.2)
    plt.tight_layout()
    plt.savefig(crosscorr_plot_filename)
    plt.show()

def plot_template(st, all_template, pairs, templ_idx, template_plot_filename):
    """
    Plot templates with an offset on the y-axis.

    Parameters:
        st (obspy.core.Stream): Seismic data streams.
        all_template (list): List of template traces.
        pairs (list): List of pairs corresponding to each template in all_template.
        templ_idx (int): Index of the template.
        template_plot_filename (str): Filename for saving the plot.

    Returns:
        None
    """
    plt.figure(figsize=(12,6))
    nb = 1  # Distance between plots
    offset = len(all_template) * nb
    x = np.linspace(0, len(all_template[0]) / st[0].stats.sampling_rate,
                    len(all_template[0]), endpoint=False)

    # Plot each template with an offset on the y-axis
    for _, (template, pair) in enumerate(zip(all_template, pairs)):
        norm = np.max(np.abs(template.data))
        plt.plot(x, template / norm + offset, label=f'{pair}')
        offset -= nb

    plt.xlabel('Time (s)', fontsize=14)
    plt.ylabel('Normalized Data + Offset', fontsize=14)
    plt.title(f'All Templates for Template {templ_idx}', fontsize=16)
    plt.yticks(np.arange(len(pairs)) * nb+nb, pairs[::-1], fontsize=12)
    plt.xlim(0, max(x))
    plt.ylim(0, len(pairs) * nb + nb)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(template_plot_filename)
    plt.close()

def plot_stacks(st, newdect, pairs, templ_idx, stack_plot_filename, cpt):
    """
    Plot the combined traces for a detection and its corresponding template.

    Parameters:
        st (obspy.core.Stream): Seismic data streams.
        newdect (numpy.ndarray): Indices of the detected events.
        pairs (list): List of pairs corresponding to each trace in st.
        templ_idx (int): Index of the template.
        stack_plot_filename (str): Filename for saving the plot.
        cpt (int): Number of the iteration for the title.

    Returns:
        None
    """
    stacked_traces = np.zeros((len(st), int(30 * st[0].stats.sampling_rate)))
    for idx, tr in enumerate(st):
        for dect in newdect:
            # Normalize each waveform by its maximum absolute amplitude
            start_time = dect  # Start from the detection point
            end_time = dect + int(30 * tr.stats.sampling_rate)  # 30-second window
            if end_time > len(tr.data):
                continue  # Skip if the window goes beyond the waveform boundaries
            waveform_window = tr.data[start_time:end_time]
            max_abs_value = np.max(np.abs(waveform_window))
            normalized_waveform = waveform_window / max_abs_value
            stacked_traces[idx, :] += normalized_waveform
    stacked_traces /= len(newdect)

    plt.figure(figsize=(12,6))
    nb = 1  # Distance between plots
    offset = len(stacked_traces) * nb
    x = np.linspace(0, 30, len(stacked_traces[0, :]), endpoint=False)

    for i in range(len(stacked_traces)):
        norm = np.max(np.abs(stacked_traces[i,:]))
        plt.plot(x, stacked_traces[i, :] / norm + offset, label=f'{pairs[i]}')
        offset -= nb

    plt.xlabel('Time (s)', fontsize=14)
    plt.ylabel('Normalized Data + Offset', fontsize=14)
    plt.title(f'Stacked Traces for Template {templ_idx} - Iteration {cpt}', fontsize=16)
    plt.yticks(np.arange(len(pairs)) * nb+nb, pairs[::-1], fontsize=12)
    plt.xlim(0, 30)
    plt.ylim(0, len(pairs) * nb + nb)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(stack_plot_filename)
    plt.show()

def plot_loc(locs, base_dir, events=None):
    """
    Create a plot of station locations and template events on a map.

    Parameters:
        locs (list): A list of tuples, where each tuple contains station name,
        longitude, and latitude.
        base_dir (str): The base directory for file paths.
        events (DataFrame or None): A DataFrame containing event data with
        columns 'lon','lat','depth', and 'datetime', or None if no events are provided.

    This function creates a scatter plot of station locations and labels them
    with station names. If events are provided, the function also plots the
    events and labels them with 'Events'. The resulting plot is saved as
    'station_events_locations_{date}.png'.

    Returns:
        None
    """
    plt.figure()

    # Separate stations by network and plot them in different colors
    for name, lon, lat, network in locs:
        if network == 'CN':
            plt.plot(lon, lat, 'bo')
        elif network == 'PB':
            plt.plot(lon, lat, 'ro')
        plt.text(lon, lat, name)
    title = 'Station Locations'
    filename = 'station_locations.png'

    # Plot events if provided
    if events:
        plt.scatter(events['lon'], events['lat'], c='grey', marker='x', label='Events')
        # plt.colorbar(scatter, label='Depth') #c='events['depth']'
        date=(UTCDateTime(events['datetime'][0]).date).strftime('%Y%m%d')
        title = f'Station and Events Locations on {date}'
        filename = 'station_events_locations_{date}.png'

    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.title(title)
    plt.savefig(os.path.join(base_dir, 'plots', filename))
    plt.show()

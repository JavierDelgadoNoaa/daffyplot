#!/usr/bin/env python

import os
import time
from math import sqrt, ceil
import math
import sys
import logging as log
from timing.date_utils import yyyymmddHHMMSS_to_epoch, yyyymmddHHMM_to_epoch, yyyymmddHH_to_epoch

'''

Contains classes and methods for reading tracker data from output files generated
by different trackers.

Javier.Delgado@noaa.gov

'''

#
# DEFINE CONSTANTS
#

# Nature run tracker data file and columns corresponding to parameters of interest
NATURE_TRACK_DATA_FILE = '/lfs1/projects/hur-aoml/lbucci/meso_osse/wrf-arw/atcf/atcfNRD03.txt'
NATURE_TRACK_DATA_FILE = '/home/Javier.Delgado/plot_testing/atcfNRD03.txt'
NATURE_DATE_IDX = 0
NATURE_maxwind_KTS_IDX = 7
NATURE_MSLP_IDX = 6
NATURE_LAT_IDX = 4
NATURE_LON_IDX = 5

# Experimenet forecast tracker data file's indices to parameters of interest
POSTPROC_DIRECTORY_PREFIX = 'POSTPROC.'
DIAPOST_DIRECTORY_NAME = 'Diapost'
DIAPOST_TRACK_FILE_NAME = 'fcst_track.d02.txt' # will look for this one first and the other as backup




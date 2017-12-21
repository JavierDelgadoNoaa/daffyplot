from date_utils import yyyymmddHHMMSS_to_epoch, yyyymmddHHMM_to_epoch, yyyymmddHH_to_epoch
from postproc.tracker_utils import ForecastTrack, get_gfdltrk_track_data

'''
Contains classes that encapsulate retrieval of tracker data from tracker output
(e.g. ATCF) files. Supports GFDL tracker and the internal tracker used for the
ARW nature run (i.e. the 'nolan' tracker)

Javier.Delgado@noaa.gov
'''

class NatureTrack:
    '''
    This class simply encapsulates the date, lat, lon, mslp, and maxwind
    of an entry of the NatureRun track (i.e. a line of ATCF output)
    '''
    def __init__(self, date, lat, lon, mslp, maxwind):
        self.output_date = date
        self.lat = lat
        self.lon = lon
        self.mslp_value = mslp
        self.maxwind_value = maxwind

class NatureTrackHelper(object):
    '''
     This class provides methods for reading the nature run ATCF. It should not
     be used directly - use the subclass pertaining to the tracker used
    '''
    def __init__(self, start_date, end_date, tracker_data_file):
        self.start_date = start_date
        self.end_date = end_date
        self.tracker_data_file = tracker_data_file
        self.nature_tracker_data = self.get_nature_track_data(start_date, end_date, tracker_data_file)


    def get_nature_track_data(self, start_date=None, end_date=None, tracker_data_file=None):
        '''
        Reads parameters from a `tracker_data_file`. The expected format for this
         file is one line per tracker entry,
        The column numbers for the fields are specified by the class fields atcf_lat_idx,
         atcf_lon_idx, atcf_maxwind_idx, atcf_mslp_idx
        RETURNS
        A dictionary mapping each tracker entry that falls between `start_date` and
         `end_date` entry date (in seconds since epoch) to a NatureTrack object
        '''
        # set defaults
        if start_date is None: start_date = self.start_date
        if end_date is None: end_date = self.end_date
        if tracker_data_file is None:
            tracker_data_file = self.tracker_data_file
        # call subclass-specific method to get track data
        nature_atcf_entries = self.read_tracker_atcf()
        #print len(nature_atcf_entries.keys())
        return nature_atcf_entries

class NatureNolanTrackHelper(NatureTrackHelper):
    def __init__(self, start_date, end_date, tracker_data_file):
        self.atcf_date_idx = 0
        self.atcf_lat_idx = 4
        self.atcf_lon_idx = 5
        self.atcf_mslp_idx = 6
        self.atcf_maxwind_idx = 7
        super(NatureNolanTrackHelper, self).__init__(start_date, end_date, tracker_data_file)

    def read_tracker_atcf(self):
        '''
        Read the tracker output file and return a dictionary mapping entry dates
        (in seconds since epoch) to NatureTrack objects that encapsulate position,
        maxwind, and mslp
        '''
        nature_atcf_entries = {}
        for line in open(self.tracker_data_file, 'r'):
            toks = line.strip().split()
            entry_date = yyyymmddHHMMSS_to_epoch(toks[self.atcf_date_idx])
            if entry_date < self.start_date or entry_date > self.end_date: continue
            nrAtcf = NatureTrack( entry_date,
                                  float(toks[self.atcf_lat_idx]),
                                  float(toks[self.atcf_lon_idx]),
                                  float(toks[self.atcf_mslp_idx])/100.0,
                                  float(toks[self.atcf_maxwind_idx]) )
            if nature_atcf_entries.has_key(entry_date):
                raise Exception('Duplicate key!: %s. There should only be one per date', entry_date)
            nature_atcf_entries[entry_date] = nrAtcf
        return nature_atcf_entries

class NatureGfdlTrackHelper(NatureTrackHelper):
    def __init__(self, start_date, end_date, tracker_data_file):
        super(NatureGfdlTrackHelper, self).__init__(start_date, end_date, tracker_data_file)

    def read_tracker_atcf(self):
        '''
        Use external function to read the gfdl tracker atcf
        RETURN
            A dictionary mapping the date from each entry in the ATCF
            to a NatureTrackobject
        '''
        fcst_trk = get_gfdltrk_track_data(self.tracker_data_file,
                                          flagged_entries_file="",
                                          include_flagged_entries=False, log=None)
        nature_atcf_entries = {}
        for trkEntry in fcst_trk.tracker_entries:
            currDate = trkEntry.get_fhr_epoch()
            if nature_atcf_entries.has_key(currDate):
                raise Exception('Duplicate key!: %s. There should only be one per date',
                                 currDate)
            nature_atcf_entries[currDate] = NatureTrack(currDate,
                                                        trkEntry.lat,
                                                        trkEntry.lon,
                                                        trkEntry.mslp_value,
                                                        trkEntry.maxwind_value)
        return nature_atcf_entries

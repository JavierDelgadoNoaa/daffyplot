#!/usr/bin/env python

"""
Utility for plotting the track of a hurricane

Javier.Delgado@noaa.gov
"""

import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.pyplot import gca
from mpl_toolkits.basemap import Basemap
#from util import get_marked_indices
from matplotlib.colors import ColorConverter
import logging as log

WEST_CORNER = -85.0
EAST_CORNER = -35.0
NORTH_CORNER = 40.0
SOUTH_CORNER = 15.0
GRIDLINE_WE = 500
GRIDLINE_NS = 500
# Coastlines and lakes with an area (in sq. km) smaller than this will not be plotted
AREA_THRESHOLD = 1000.
# Map resolution should be (c)rude, (l)ow, intermediate, high, full, or None
MAP_RESOLUTION = 'l'
# Map projection - only 'cyl' is tested
MAP_PROJECTION = 'cyl'

TRACK_LINE_COLOR = '#ffffff'
TRACK_LINE_WIDTH = 1.5

# How frequently to create markers indicating time
TIME_MARKER_INTERVAL=24 # daily

def plot_track(lats, lons, **kwargs):
    '''
    Given a list of latitudes and a list of longitudes corresponding to
    a hurricane track, plot the track using Basemap.

    REQUIRED ARGUMENTS
     - lats - List of latitude points
     - lons - List of longitude points

    OPTIONAL KEYWORD ARGUMENTS (and their corresponding functionality):
     - line_color - Color to use for the line. Default: black
     - line_width - Width to use for the line: Default: 1.5
     - line_style  - Line style. Default: solid
     - zorder - Z order of the line. Default: 0
     - label - label to apply to the data being passed
     - windspeeds - List of windspeeds corresponding to the lat/lon pairs.
                    If set, the shade of the track lines will be adjusted
                    according to the strength of the storm.
                    *NOTE: The scheme for this is currently very crude*
     - flagged_idc - List of indices in the lat/lon that are marked as
                     flagged. If passed in, these points will be indicated
                     using circular markers
     - ax - Axes object to plot on. This overrides the 'basemap' argument.
     - basemap - If set, use it as the Basemap object for plotting.
                 Otherwise instantiate a new one.
     - extents - If set and basemap is not passed in, use these extents
                 for the map. Should be a 4-element list as follows:
                     [lowerLat, westLon, upperLat, eastLon]
                 If not passed in, use the global variables defined in
                 this module
     - indicator_freq - If set, mark points corresponding to this
                        interval.
                        e.g. if passing in values ever 6 hours and you want
                        to indicate every 24 hours, set this to 4
     - ns_gridline_freq - Interval (in degrees) at which to show north->south
                          gridlines
     - we_gridline_freq - Interval (in degrees) at which to show west->east
                          gridlines
     - alpha - Alpha level to use for the line
     - draw_coastlines - Draw lines separating water from land? (Default: True)
     - draw_countries - Show the countries? (Default: True)
     - water_color - Colorize bodies of water? Default: Just leave it
                     as background color (white)
     - lake_color - Color to use for lakes within continents. Default: Leave as
                    background color.
     - continent_color - Color to use for continents. Default: white

     *NOTE: For b/w figure, only set draw_coastlines to True

    '''
    # Set basic optional values

    # array of arguments to pass to the plot() call
    mpl_plot_kwargs = {}

    if kwargs.has_key('line_color'):
        line_color = kwargs['line_color']
    else:
        line_color = TRACK_LINE_COLOR
    if kwargs.has_key('line_style'):
        line_style=kwargs['line_style']
    else:
        line_style = '-'
    if kwargs.has_key('zorder'):
        zorder = kwargs['zorder']
    else:
        zorder=0
    if kwargs.has_key('alpha'):
        line_alpha = kwargs['alpha']
    else:
        line_alpha = 1.0
    if kwargs.has_key('line_width'):
        line_width = kwargs['line_width']
    else:
        line_width = TRACK_LINE_WIDTH
    if kwargs.has_key('label'):
        mpl_plot_kwargs['label'] = kwargs['label']
    # sanity checks
    assert len(lats) == len(lons)

    # Set the axes
    if kwargs.has_key('ax'):
        ax = kwargs['ax']
    else:
        ax = gca()

    # Instantiate/set the Basemap object
    if kwargs.has_key('basemap'):
        m = kwargs['basemap']
    else:
        if kwargs.has_key('extents'):
            lowerLat = kwargs['extents'][0]
            westLon = kwargs['extents'][1]
            upperLat = kwargs['extents'][2]
            eastLon = kwargs['extents'][3]
        else:
            lowerLat = SOUTH_CORNER
            westLon = WEST_CORNER
            upperLat = NORTH_CORNER
            eastLon = EAST_CORNER
        m = Basemap(llcrnrlon=westLon,llcrnrlat=lowerLat,
                    urcrnrlon=eastLon,urcrnrlat=upperLat,
                    projection=MAP_PROJECTION, resolution=MAP_RESOLUTION,
                    area_thresh=AREA_THRESHOLD,
                    ax=ax)

    #
    # plot track
    #
    maxwinds = []
    if kwargs.has_key('windspeeds'):
        maxwinds = kwargs['windspeeds']
        assert len(maxwinds) == len(lats)
        rgb = ColorConverter().to_rgb(line_color)
        max_maxwind = max(maxwinds)
    # To support different colors depending on speed, we need to plot multiple
    # small lines. Due to a technicality in Basemap::plot, we need to
    # plot in increments of at least 3 points. As a result, the last two points'
    # wind speed will not affect the line color
    # NOTE That since all points (except the first and last 2) are being plotted
    # multiple times, the effect of different colors/alphas is greatly diminished.
    # a better temporary scheme is to only do each 3-point 'subline' once
    # and use the average of the 3 points' maxwind values to determine the shading.
    #for i in range(len(lats) - 2):
    subline_length = 3
    for i in range(0, len(lats) - 2, subline_length):
        # if next subline would have less than 3 elements, extend the
        # current subline correspondingly
        if (i+subline_length) >= ( len(lats) - (subline_length - 1) ):
            subline_length = subline_length + (len(lats) % subline_length)
        if len(maxwinds) > 0:
            #scale_factor = maxwinds[i] / max_maxwind
            scale_factor = np.mean(maxwinds[i:i+subline_length+1]) / max_maxwind
            # This scheme only works with black and other mixed colors...
            # not the common red,green,blue, etc.
            #currColor = [ max(0,c - scale_factor) for c in rgb]
            #print currColor
            # for now, just use alpha
            if line_alpha != 1:
                log.debug('Note: currently using a crude scheme for line color'\
                       ' that just modifies the alpha')
            currColor = line_color
            line_alpha =  scale_factor
            log.debug(line_alpha)
        else:
            currColor = line_color
        m.plot(lons[i:i+subline_length+1], lats[i:i+subline_length+1],
               latlon=True, color=currColor,
               linewidth=line_width, alpha=line_alpha, ls=line_style,
               zorder=zorder,
               **mpl_plot_kwargs)

    # plot markers on flagged points - this is slow!
    if kwargs.has_key('flagged_idc') and len(kwargs['flagged_idc']) > 0:
        # Due to an issue with Basemap, cannot indicate flagged
        # indices unless there are at least 3 of them, so pad the list
        if len(kwargs['flagged_idc']) < 3:
            flagged_idc = kwargs['flagged_idc']
            flagged_idc.append(flagged_idc[0])
            flagged_idc.append(flagged_idc[0])
        flaggedLats = []
        flaggedLons = []
        for x in kwargs['flagged_idc']:
            flaggedLats.append(lats[x])
            flaggedLons.append(lons[x])
        m.scatter(flaggedLons, flaggedLats, latlon=True, s=35.0,
                  #facecolors='none', edgecolors=line_color)
                  facecolors='red', edgecolors=line_color)

    # plot markers every 24 hours
    if kwargs.has_key('indicator_freq'):
        for i in kwargs['indicator_freq']:
            m.scatter(lons[i], lats[i], latlon=True, color=line_color, s=10.0)
    # make color coded line, with higher wind speeds having darker color

    # draw coastlines, meridians and parallels.
    if kwargs.has_key('draw_coastlines') and not kwargs('draw_coastlines'):
        pass
    else:
        m.drawcoastlines()
    if kwargs.has_key('draw_countries') and not kwargs('draw_countries'):
        pass
    else:
        m.drawcountries()
    if kwargs.has_key('water_color'):
        m.drawmapboundary(fill_color=kwargs['water_color'])
    if kwargs.has_key('lake_color') or kwargs.has_key('continent_color'):
        if not kwargs.has_key('continent_color'):
            m.fillcontinents(lake_color=kwargs['lake_color'], color='white')
        elif not kwargs.has_key('lake_color'):
            m.fillcontinents(color=kwargs['continent_color'])
        else:
            m.fillcontinents(color=kwargs['continent_color'],
                             lake_color=kwargs['lake_color'])
    if kwargs.has_key('ns_gridline_freq'):
        m.drawparallels(np.arange(lowerLat,upperLat,kwargs['ns_gridline_freq']),
                        labels=[1,1,0,0])
    if kwargs.has_key('we_gridline_freq'):
        m.drawmeridians(np.arange(westLon,eastLon,kwargs['we_gridline_freq']),
                        labels=[0,0,0,1])


##
# TEST
##
if __name__ == '__main__':
    try:
        from tracker_utils import ForecastTrack, get_diapost_track_data,\
                                  get_gfdltrk_track_data
    except:
        print 'The previous directory needs to be in your PYTHONPATH'
        print 'If running within DaffyPlot, source the env.sh file'
        sys.exit(1)

    log.basicConfig(level=log.DEBUG)
    forecast_track = get_gfdltrk_track_data('sample_fort.64')
    lons = [entry.lon for entry in forecast_track.tracker_entries]
    lats = [entry.lat for entry in forecast_track.tracker_entries]
    fhrs = [entry.fhr for entry in forecast_track.tracker_entries]
    maxwinds = [entry.maxwind_value for entry in forecast_track.tracker_entries]
    flagged = [entry.flagged for entry in forecast_track.tracker_entries]
    #flagged_idc = get_marked_indices(flagged)
    flagged_idc = [ i for i,v in enumerate(flagged) if v is True ]
    #flagged_idc = [1]
    #print track
    day_idc = [ idx for idx,val in enumerate(fhrs) if val%TIME_MARKER_INTERVAL == 0 ]
    plot_track(lats, lons, windspeeds=maxwinds, indicator_freq=day_idc,
               line_color='black', ns_gridline_freq=10, we_gridline_freq=10,
               flagged_idc=flagged_idc)
    # options worth testing: water_color='#99ffff',lake_color='#99ffff', continent_color='#cc9966'
    plt.savefig('track.png')

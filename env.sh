export NWPY_ENV=/home/Javier.Delgado/libs/nwpy/etc/env.sh
export PYCANE_DIST=/home/Javier.Delgado/apps/pycane_dist/master
export PYHWRF_DIST=/home/Javier.Delgado/apps/pyhwrf/emc/dist/bleeding_edge

pycane_env=$PYCANE_DIST/etc/env.sh
pyhwrf_libs=$PYHWRF_DIST/ush

if [[ ! -e $NWPY_ENV ]] ; then
    echo -e "Nwpy env file not found at: $NWPY_ENV.\nPlease check paths"
else
    source $NWPY_ENV 
fi
if [[ ! -e $pycane_env ]] ; then
    echo -e "Pycane env file not found, scripts may fail.\nCheck \$PYCANE_DIST"
else
    source $pycane_env 
fi
if [[ ! -d $pyhwrf_libs ]] ; then
    echo -e "PyHWRF 'ush' directory not found.\nCheck $PYHWRF_DIST"
else
    export PYTHONPATH=$PYTHONPATH:$pyhwrf_libs
fi

export PYTHONPATH=$PYTHONPATH:`pwd`/extern/postproc:`pwd`/extern:$PYTHONPATH

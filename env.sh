export PYCANE_DIST=/home/Javier.Delgado/apps/pycane_dist/master
export PYHWRF_DIST=/home/Javier.Delgado/apps/pyhwrf/emc/dist/bleeding_edge

pycane_env=$PYCANE_DIST/etc/env.sh
pyhwrf_libs=$PYHWRF_DIST/ush

if [[ ! -e $pycane_env ]] ; then
    echo "Pycane env file not found, scripts may fail. Check \$PYCANE_DIST"
else
    source $pycane_env 
fi
if [[ ! -d $pyhwrf_libs ]] ; then
    echo "PyHWRF 'ush' directory not found. Check $PYHWRF_DIST"
else
    export PYTHONPATH=$PYTHONPATH:$pyhwrf_libs
fi

export PYTHONPATH=$PYTHONPATH:`pwd`/extern/postproc:`pwd`/extern:$PYTHONPATH

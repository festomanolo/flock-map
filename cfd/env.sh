# Debian/Ubuntu openfoam v1912 package: minimal environment (the shipped bashrc is incomplete)
export WM_PROJECT=OpenFOAM WM_PROJECT_VERSION=v1912 FOAM_API=1912
export WM_PROJECT_DIR=/usr/share/openfoam
export FOAM_ETC=/usr/share/openfoam/etc
export FOAM_APPBIN=/usr/bin FOAM_LIBBIN=/usr/lib FOAM_USER_APPBIN=/usr/bin FOAM_USER_LIBBIN=/usr/lib
export WM_COMPILER=Gcc WM_PRECISION_OPTION=DP WM_LABEL_SIZE=32 WM_MPLIB=SYSTEMOPENMPI
export LD_LIBRARY_PATH=/usr/lib:/usr/lib/dummy:$LD_LIBRARY_PATH
export FOAM_SIGFPE=1
export OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1

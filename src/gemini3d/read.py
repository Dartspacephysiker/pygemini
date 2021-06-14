"""
struct manpage:
https://docs.python.org/3/library/struct.html#struct-format-strings
"""

from __future__ import annotations
import numpy as np
from pathlib import Path
from datetime import datetime
import typing as T
import xarray

from .config import read_ini, read_nml
from . import find
from . import matlab
from . import LSP

from .raw import read as raw_read
from .hdf5 import read as h5read
from .nc4 import read as ncread


# do NOT use lru_cache--can have weird unexpected effects with complicated setups
def config(path: Path) -> dict[str, T.Any]:
    """
    read simulation input configuration

    .nml is strongly preferred, .ini is legacy.

    Parameters
    ----------
    path: pathlib.Path
        config file path

    Returns
    -------
    params: dict
        simulation parameters from config file
    """

    file = find.config(path, required=True)

    if file.suffix == ".ini":
        P = read_ini(file)
    else:
        P = read_nml(file)

    return P


def simsize(path: Path, suffix: str = None) -> tuple[int, ...]:
    """get simulation dimensions"""

    fn = find.simsize(path, suffix=suffix, required=True)

    if fn.suffix == ".h5":
        return h5read.simsize(fn)
    elif fn.suffix == ".nc":
        return ncread.simsize(fn)
    elif fn.suffix == ".dat":
        return raw_read.simsize(fn)
    elif fn.suffix == ".mat":
        return matlab.simsize(fn)
    else:
        raise ValueError("unknown simsize file type")


def grid(
    path: Path, *, var: set[str] = None, file_format: str = None, shape: bool = False
) -> dict[str, T.Any]:
    """
    get simulation grid

    Parameters
    ----------

    path: pathlib.Path
        path to simgrid.*
    var: set of str
        read only these grid variables
    file_format: str, optional
        force .h5, .nc, .dat (debugging)
    shape: bool, optional
        read only the shape of the grid instead of the data iteslf
    """

    fn = find.grid(path, required=True)

    if not file_format:
        file_format = fn.suffix[1:]

    if file_format == "dat":
        xg = raw_read.grid(fn.with_suffix(".dat"), shape=shape)
    elif file_format == "h5":
        xg = h5read.grid(fn.with_suffix(".h5"), var=var, shape=shape)
    elif file_format == "nc":
        xg = ncread.grid(fn.with_suffix(".nc"), var=var, shape=shape)
    elif file_format == "mat":
        xg = matlab.grid(fn.with_suffix(".mat"), shape=shape)
    else:
        raise ValueError(f"Unknown file type {fn}")

    xg["filename"] = fn

    return xg


def data(
    fn: Path, var: set[str] = None, *, file_format: str = None, cfg: dict[str, T.Any] = None
) -> xarray.Dataset:
    """
    knowing the filename for a simulation time step, read the data for that time step

    Parameters
    ----------
    fn: pathlib.Path
        filename for this timestep
    var: set of set
        variables to use
    file_format: str
        specify file extension of data files
    cfg: dict
        to avoid reading config.nml
    E0dir: pathlib.Path
        E0 directory

    Returns
    -------
    dat: xarray.Dataset
        simulation outputs
    """

    if not var:
        var = {"ne", "Ti", "Te", "v1", "v2", "v3", "J1", "J2", "J3", "Phi"}

    if isinstance(var, str):
        var = [var]
    var = set(var)

    fn = Path(fn).expanduser()

    if not cfg:
        cfg = config(fn.parent)

    if not file_format:
        file_format = cfg["file_format"] if "file_format" in cfg else fn.suffix[1:]

    if file_format == "dat":
        flag = cfg.get("flagoutput")
        if flag == 0:
            dat = raw_read.frame3d_curvne(fn)
        elif flag == 1:
            dat = raw_read.frame3d_curv(fn)
        elif flag == 2:
            dat = raw_read.frame3d_curvavg(fn)
        else:
            raise ValueError(f"Unsure how to read {fn} with flagoutput {flag}")
    elif file_format == "h5":
        flag = h5read.flagoutput(fn, cfg)

        if flag == 0:
            dat = h5read.frame3d_curvne(fn)
        elif flag == 1:
            dat = h5read.frame3d_curv(fn, var)
        elif flag == 2:
            dat = h5read.frame3d_curvavg(fn, var)
        else:
            raise ValueError(f"Unsure how to read {fn} with flagoutput {flag}")
    elif file_format == "nc":
        flag = ncread.flagoutput(fn, cfg)

        if flag == 0:
            dat = ncread.frame3d_curvne(fn)
        elif flag == 1:
            dat = ncread.frame3d_curv(fn, var)
        elif flag == 2:
            dat = ncread.frame3d_curvavg(fn, var)
        else:
            raise ValueError(f"Unsure how to read {fn} with flagoutput {flag}")
    else:
        raise ValueError(f"Unknown file type {fn}")

    lx = (dat.dims["x1"], dat.dims["x2"], dat.dims["x3"])

    # %% Derived variables
    if flag == 1:
        if {"ne", "v1", "Ti", "Te"} & var:
            dat["ne"] = (("x1", "x2", "x3"), dat["ns"][LSP - 1, :, :, :].data)
            # np.any() in case neither is an np.ndarray
            if dat["ns"].shape[0] != LSP or not np.array_equal(dat["ns"].shape[1:], lx):
                raise ValueError(
                    f"may have wrong permutation on read. lx: {lx}  ns x1,x2,x3: {dat['ns'].shape}"
                )
        if "v1" in var:
            dat["v1"] = (
                ("x1", "x2", "x3"),
                (dat["ns"][:6, :, :, :] * dat["vs1"][:6, :, :, :]).sum(axis=0).data
                / dat["ne"].data,
            )
        if "Ti" in var:
            dat["Ti"] = (
                ("x1", "x2", "x3"),
                (dat["ns"][:6, :, :, :] * dat["Ts"][:6, :, :, :]).sum(axis=0).data / dat["ne"].data,
            )
        if "Te" in var:
            dat["Te"] = (("x1", "x2", "x3"), dat["Ts"][LSP - 1, :, :, :].data)

        if "J1" in var:
            # np.any() in case neither is an np.ndarray
            if np.any(dat["J1"].shape != lx):
                raise ValueError("J1 may have wrong permutation on read")

    if "time" not in dat:
        dat = dat.assign_coords({"time": time(fn)})

    return dat


def glow(fn: Path) -> xarray.DataArray:

    fmt = fn.suffix

    if fmt == ".h5":
        dat = h5read.glow_aurmap(fn)
    elif fmt == ".nc":
        dat = ncread.glow_aurmap(fn)
    elif fmt == ".dat":
        dat = raw_read.glow_aurmap(fn)
    else:
        raise ValueError(f"Unknown file type {fn}")

    return dat


def Efield(fn: Path, *, file_format: str = None) -> dict[str, T.Any]:
    """load Efield data "Efield_inputs"

    Parameters
    ----------
    fn: pathlib.Path
        filename for this timestep

    Returns
    -------
    dat: dict of np.ndarray
        electric field
    """

    if not fn:
        return {}

    fn = Path(fn).expanduser().resolve(strict=True)

    if not file_format:
        file_format = fn.suffix[1:]

    if file_format == "h5":
        E = h5read.Efield(fn)
    elif file_format == "nc":
        E = ncread.Efield(fn)
    elif file_format == "dat":
        E = raw_read.Efield(fn)
    else:
        raise ValueError(f"Unknown file type {fn}")

    return E


def precip(fn: Path, *, file_format: str = None) -> dict[str, T.Any]:
    """load precipitation to disk

    Parameters
    ----------
    fn: pathlib.Path
        path to precipitation file
    file_format: str
        file format to read

    Returns
    -------
    dat: dict
        precipitation
    """

    if not fn:
        return {}

    fn = Path(fn).expanduser().resolve(strict=True)

    if not file_format:
        file_format = fn.suffix[1:]

    if file_format == "h5":
        dat = h5read.precip(fn)
    elif file_format == "nc":
        dat = ncread.precip(fn)
    else:
        raise ValueError(f"unknown file format {file_format}")

    return dat


def frame(
    simdir: Path, time: datetime, *, var: set[str] = None, file_format: str = None
) -> xarray.Dataset:
    """
    load a frame of simulation data, automatically selecting the correct
    functions based on simulation parameters

    Parameters
    ----------
    simdir: pathlib.Path
        top-level directory of simulation output
    time: datetime.datetime
        time to load from simulation output
    var: set of str
        variable(s) to read
    file_format: str, optional
        "hdf5", "nc" for hdf5 or netcdf4 respectively

    Returns
    -------
    dat: xarray.Dataset
        simulation output for this time step
    """

    return data(
        find.frame(simdir, time, file_format=file_format, required=True),
        var=var,
        file_format=file_format,
    )


def time(file: Path) -> datetime:
    """
    read simulation time of a file
    """

    if file.suffix == ".h5":
        t = h5read.time(file)
    elif file.suffix == ".nc":
        t = ncread.time(file)
    else:
        raise ValueError(f"unknown file format {file.suffix}")

    return t


def get_lxs(xg: dict[str, T.Any]) -> tuple[int, int, int]:

    lx = None
    for k in ("lx", "lxs", "lx1"):
        if k in xg:
            if k == "lx1":
                lx = [xg["lx1"], xg["lx2"], xg["lx3"]]
                break
            else:
                lx = xg[k]

    if lx is None:
        raise IndexError("Did not find grid size")

    return lx[0], lx[1], lx[2]

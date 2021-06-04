from __future__ import annotations
from pathlib import Path
import typing as T
from datetime import datetime

import numpy as np
import matplotlib as mpl

from .. import read
from ..utils import to_datetime
from .core import save_fig
from .glow import glow
from .constants import PARAMS
from . import cartesian
from . import curvilinear

mpl.rcParams["axes.formatter.limits"] = (-3, 4)
mpl.rcParams["axes.formatter.useoffset"] = False
mpl.rcParams["axes.formatter.min_exponent"] = 4


def grid2plotfun(xg: dict[str, np.ndarray]):
    plotfun = None
    h1 = xg.get("h1")

    lxs = read.get_lxs(xg)

    if h1 is not None:
        minh1 = h1.min()
        maxh1 = h1.max()
        if (abs(minh1 - 1) > 1e-4) or (abs(maxh1 - 1) > 1e-4):  # curvilinear grid
            if (lxs[1] > 1) and (lxs[2] > 1):
                plotfun = curvilinear.curv3d_long
            else:
                plotfun = curvilinear.curv2d

    if plotfun is None:
        if (lxs[1] > 1) and (lxs[2] > 1):
            plotfun = cartesian.cart3d_long_ENU
        else:
            plotfun = cartesian.cart2d

    return plotfun


def plot_all(direc: Path, var: set[str] = None, saveplot_fmt: str = None):

    direc = Path(direc).expanduser().resolve(strict=True)

    if not var:
        var = PARAMS

    if not {"png", "pdf", "eps"} & var:
        raise ValueError("please use saveplot_fmt='png' or similar for plot format")

    xg = read.grid(direc)
    plotfun = grid2plotfun(xg)
    cfg = read.config(direc)

    aurmap_dir = None
    if cfg.get("aurmap_dir"):
        # handle relative or absolute path to GLOW data
        if cfg["aurmap_dir"].is_absolute():
            aurmap_dir = cfg["aurmap_dir"]
        else:
            aurmap_dir = direc / cfg["aurmap_dir"]

    # %% loop over files / time
    for t in cfg["time"]:
        frame(direc, time=t, var=var, saveplot_fmt=saveplot_fmt, xg=xg, plotfun=plotfun)
        glow(aurmap_dir, t, saveplot_fmt, xg=xg)


def frame(
    direc: Path,
    time: datetime = None,
    *,
    plotfun: T.Callable = None,
    saveplot_fmt: str = None,
    var: set[str] = None,
    xg: dict[str, T.Any] = None,
):
    """
    if save_dir, plots will not be visible while generating to speed plot writing
    """

    if not var:
        var = PARAMS

    file = None
    if time is None:
        if not direc.is_file():
            raise ValueError("must either specify directory and time, or single file")
        file = direc
        direc = direc.parent

    if not xg:
        xg = read.grid(direc)

    if file is None:
        dat = read.frame(direc, time, var=var)
    else:
        dat = read.data(file, var)

    if not dat:
        raise ValueError(f"No data in {direc} at {time}")

    if plotfun is None:
        plotfun = grid2plotfun(xg)

    for k, v in dat.items():
        if any(s in k for s in var):
            fg = plotfun(
                to_datetime(dat.time), xg, v.squeeze(), k, wavelength=dat.get("wavelength")
            )
            save_fig(fg, direc, name=k, fmt=saveplot_fmt, time=time)

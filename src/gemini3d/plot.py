import argparse
from pathlib import Path

from . import read
from .vis import plotframe


def cli():
    p = argparse.ArgumentParser()
    p.add_argument("direc", help="directory to plot")
    p.add_argument("--mayavi", help="do 3D Mayavi plots", action="store_true")
    p.add_argument("-s", "--saveplots", help="save plots to data directory", action="store_true")
    p.add_argument("--only", help="only plot these quantities", nargs="+")
    p = p.parse_args()

    if p.mayavi:
        from . import vis3d
        from mayavi.mlab import show
    else:
        from matplotlib.pyplot import show

    direc = Path(p.direc).expanduser().resolve(strict=True)
    if p.saveplots:
        from matplotlib.figure import Figure

        fg = Figure(constrained_layout=True)
        save_dir = direc / "plots"
        save_dir.mkdir(parents=True, exist_ok=True)
    else:
        fg = None
        save_dir = None

    grid = read.grid(direc)

    flist = sorted(direc.glob("*.h5"))
    if len(flist) == 0:
        flist = sorted(direc.glob("*.dat"))
    # %% loop over files / time
    for file in flist:
        try:
            dat = read.data(file)
        except Exception as e:
            print(f"SKIP: {file}   {e}")
            continue
        if "mlon" in dat and "mlon" not in grid:
            grid["mlon"] = dat["mlon"]
            grid["mlat"] = dat["mlat"]

        if p.mayavi:
            vis3d.plotframe(grid, dat, params=p.only, save_dir=save_dir)
        else:
            plotframe(grid, dat, params=p.only, save_dir=save_dir, fg=fg)

        if p.saveplots:
            print(f"{dat['time']} => {save_dir}")
        else:
            show()


if __name__ == "__main__":
    cli()

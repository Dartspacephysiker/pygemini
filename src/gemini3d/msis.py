"""
using MSIS Fortran exectuable from Python
"""

import os
import tempfile
from pathlib import Path
import numpy as np
import subprocess
import logging
import typing as T
import importlib.resources

from . import cmake


def msis_setup(p: T.Dict[str, T.Any], xg: T.Dict[str, T.Any]) -> np.ndarray:
    """calls MSIS Fortran exectuable
    compiles if not present

    [f107a, f107, ap] = activ
        COLUMNS OF DATA:
          1 - ALT
          2 - HE NUMBER DENSITY(M-3)
          3 - O NUMBER DENSITY(M-3)
          4 - N2 NUMBER DENSITY(M-3)
          5 - O2 NUMBER DENSITY(M-3)
          6 - AR NUMBER DENSITY(M-3)
          7 - TOTAL MASS DENSITY(KG/M3)
          8 - H NUMBER DENSITY(M-3)
          9 - N NUMBER DENSITY(M-3)
          10 - Anomalous oxygen NUMBER DENSITY(M-3)
          11 - TEMPERATURE AT ALT

    """

    msis_stem = "msis_setup"
    msis_name = msis_stem
    if os.name == "nt":
        msis_name += ".exe"

    msis_pipe = True

    if not importlib.resources.is_resource(__package__, msis_name):
        with importlib.resources.path(__package__, "CMakeLists.txt") as setup:
            cmake.build(
                setup.parent,
                setup.parent / "build",
                config_args=["-DBUILD_TESTING:BOOL=false"],
                build_args=["--target", msis_stem],
            )

    # %% SPECIFY SIZES ETC.
    lx1 = xg["lx"][0]
    lx2 = xg["lx"][1]
    lx3 = xg["lx"][2]
    alt = xg["alt"] / 1e3
    glat = xg["glat"]
    glon = xg["glon"]
    lz = lx1 * lx2 * lx3
    # % CONVERT DATES/TIMES/INDICES INTO MSIS-FRIENDLY FORMAT
    t0 = p["time"][0]
    doy = int(t0.strftime("%j"))
    UTsec0 = t0.hour * 3600 + t0.minute * 60 + t0.second + t0.microsecond / 1e6

    logging.debug(f"MSIS00 using DOY: {doy}")
    # %% KLUDGE THE BELOW-ZERO ALTITUDES SO THAT THEY DON'T GIVE INF
    alt[alt <= 0] = 1
    # %% CREATE INPUT FILE FOR FORTRAN PROGRAM
    if msis_pipe:
        invals = (
            f"{doy}\n{int(UTsec0)}\n{p['f107a']} {p['f107']} {p['Ap']} {p['Ap']}\n{lz}\n"
            + " ".join(map(str, glat.ravel(order="C")))
            + "\n"
            + " ".join(map(str, glon.ravel(order="C")))
            + "\n"
            + " ".join(map(str, alt.ravel(order="C")))
        )
        # the "-" means to use stdin, stdout
        args = ["-", "-", str(lz)]
        stdout = subprocess.PIPE
    else:
        invals = None
        # don't use NamedTemporaryFile because PermissionError on Windows
        file_in = Path(tempfile.gettempdir(), "msis_setup_in.dat")
        file_out = Path(tempfile.gettempdir(), "msis_setup_out.dat")
        with file_in.open("w") as f:
            np.array(doy).astype(np.int32).tofile(f)
            np.array(UTsec0).astype(np.int32).tofile(f)
            np.asarray([p["f107a"], p["f107"], p["Ap"], p["Ap"]]).astype(np.float32).tofile(f)
            np.array(lz).astype(np.int32).tofile(f)
            np.array(glat).astype(np.float32).tofile(f)
            np.array(glon).astype(np.float32).tofile(f)
            np.array(alt).astype(np.float32).tofile(f)
        args = [str(file_in), str(file_out), str(lz)]
        stdout = None

    with importlib.resources.path("gemini3d.build", msis_name) as exe:
        if "msis_version" in p:
            args.append(str(p["msis_version"]))
        cmd = [str(exe)] + args
        logging.info(" ".join(cmd))
        ret = subprocess.run(cmd, input=invals, stdout=stdout, text=True, cwd=exe.parent)

    if ret.returncode == 20:
        raise RuntimeError("Need to compile with 'cmake -Dmsis20=true'")
    if ret.returncode != 0:
        raise RuntimeError(f"MSIS failed to run: {ret.stdout}")

    Nread = lz * 11

    if msis_pipe:
        msisdat = np.fromstring(ret.stdout, np.float32, Nread, sep=" ").reshape((11, lz), order="F")
    else:
        fout_size = file_out.stat().st_size
        if fout_size != Nread * 4:
            raise RuntimeError(f"expected {file_out} size {Nread*4} but got {fout_size}")
        msisdat = np.fromfile(file_out, np.float32, Nread)

    # %% ORGANIZE
    # altitude is a useful sanity check as it's very regular and obvious.
    alt_km = msisdat[0, :].reshape((lx1, lx2, lx3))
    if not np.allclose(alt_km, alt, atol=0.02):  # atol due to precision of stdout ~0.01 km
        raise ValueError("was msis_driver output parsed correctly?")

    if not msis_pipe:
        file_in.unlink()
        file_out.unlink()

    nO = msisdat[2, :].reshape((lx1, lx2, lx3))
    nN2 = msisdat[3, :].reshape((lx1, lx2, lx3))
    nO2 = msisdat[4, :].reshape((lx1, lx2, lx3))
    Tn = msisdat[10, :].reshape((lx1, lx2, lx3))
    nN = msisdat[8, :].reshape((lx1, lx2, lx3))

    nNO = 0.4 * np.exp(-3700 / Tn) * nO2 + 5e-7 * nO
    # Mitra, 1968
    nH = msisdat[7, :].reshape((lx1, lx2, lx3))
    natm = np.stack((nO, nN2, nO2, Tn, nN, nNO, nH), 0)

    return natm

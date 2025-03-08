# ruff: noqa: D103, D101, D102
"""Use kfactory to generate a spiral sweep."""

from functools import partial
from typing import Literal

import kfactory as kf
import numpy as np


class LayerInfos(kf.LayerInfos):
    WG: kf.kdb.LayerInfo = kf.kdb.LayerInfo(1, 0)
    SHALLOW_ETCH: kf.kdb.LayerInfo = kf.kdb.LayerInfo(2, 6)
    WGCLAD: kf.kdb.LayerInfo = kf.kdb.LayerInfo(111, 0)
    BORDER: kf.kdb.LayerInfo = kf.kdb.LayerInfo(10, 0)
    FIBER_LAUNCH: kf.kdb.LayerInfo = kf.kdb.LayerInfo(99, 0)


LAYER = LayerInfos()
kf.kcl.infos = LAYER

bend = kf.cells.circular.bend_circular(width=1, radius=10, layer=LAYER.WG)
bend180 = kf.cells.circular.bend_circular(width=1, radius=10, layer=LAYER.WG, angle=180)


s_f = partial(kf.cells.straight.straight, layer=LAYER.WG)
s_f_dbu = partial(kf.cells.straight.straight_dbu, layer=LAYER.WG)


rib_enc = kf.LayerEnclosure(
    sections=[(LAYER.WGCLAD, 500)],
    name="RIB",
    main_layer=LAYER.WG,
    kcl=kf.kcl,
)

ridge_enc = kf.LayerEnclosure(
    sections=[],
    name="RIDGE",
    main_layer=LAYER.WG,
    kcl=kf.kcl,
)


@kf.cell
def mmi(
    taper_length: int = 2000,
    taper_width1: int = 1000,
    taper_width2: int = 15000,
    body_width: int = 2000,
    body_length: int = 12000,
) -> kf.KCell:
    """Create a MMI cell.

    Args:
        taper_length: Length of the taper.
        taper_width1: Width of the taper at the input.
        taper_width2: Width of the taper at the output.
        body_width: Width of the MMI body.
        body_length: Length of the MMI body.
    """
    c = kf.KCell()

    c.shapes(LAYER.WG).insert(kf.kdb.Box(12_000, 4_000))
    poly = kf.kdb.Polygon(
        [
            kf.kdb.Point(-2000, -500),
            kf.kdb.Point(-2000, 500),
            kf.kdb.Point(0, 750),
            kf.kdb.Point(0, -750),
        ]
    )
    c.shapes(LAYER.WG).insert(poly.transformed(kf.kdb.Trans(0, False, -6_000, 1_000)))
    c.shapes(LAYER.WG).insert(poly.transformed(kf.kdb.Trans(0, False, -6_000, -1_000)))
    c.shapes(LAYER.WG).insert(poly.transformed(kf.kdb.Trans(2, False, 6_000, 0)))

    c.create_port(
        trans=kf.kdb.Trans(2, False, -8_000, -1000), width=1000, layer_info=LAYER.WG
    )
    c.create_port(
        trans=kf.kdb.Trans(2, False, -8_000, 1000), width=1000, layer_info=LAYER.WG
    )
    c.create_port(trans=kf.kdb.Trans(8_000, 0), width=1000, zv=LAYER.WG)
    c.autorename_ports()

    return c


@kf.cell
def mzi(delta_l: int) -> kf.KCell:
    c = kf.KCell()
    mmi1 = c << mmi()
    mmi2 = c << mmi()

    b1 = c << bend
    b1.connect("o1", mmi1, "o2", mirror=True)
    b2 = c << bend180
    b3 = c << bend

    s = s_f(width=1, length=delta_l / 2)
    s1 = c << s
    s2 = c << s
    s1.connect("o1", b1, "o2")
    b2.connect("o2", s1, "o2")
    s2.connect("o1", b2, "o1")
    b3.connect("o1", s2, "o2")
    mmi2.connect("o2", b3, "o2")

    b1 = c << bend
    b2 = c << bend180
    b3 = c << bend

    b1.connect("o1", mmi1, "o1")
    b2.connect("o2", b1, "o2")
    b3.connect("o1", b2, "o1")

    c.add_port(mmi1.ports["o3"])
    c.add_port(mmi2.ports["o3"])
    c.autorename_ports()

    return c


@kf.cell
def mzi_test(delta_l: int) -> kf.KCell:
    c = kf.KCell()

    gcs = [
        c
        << grating_coupler_elliptical_te(
            wg_width=1,
        )
        for _ in range(4)
    ]
    for i in range(4):
        gc = gcs[i]
        gc.rotate(3)
        gc.movex(200000 * i)

    mzi1 = c << mzi(delta_l=delta_l)
    mzi1.move((mzi1.bbox().center().x, mzi1.bbox().bottom), (300000, 20_000))
    kf.routing.optical.route(
        c,
        mzi1.ports["o1"],
        gcs[1].ports["o1"],
        straight_factory=s_f_dbu,
        bend90_cell=bend,
    )
    kf.routing.optical.route(
        c,
        mzi1.ports["o2"],
        gcs[2].ports["o1"],
        straight_factory=s_f_dbu,
        bend90_cell=bend,
    )

    kf.routing.optical.place90(
        c,
        gcs[0].ports["o1"],
        gcs[3].ports["o1"],
        kf.routing.optical.route_loopback(
            gcs[0].ports["o1"],
            gcs[3].ports["o1"],
            bend90_radius=10_000,
            # bend180_radius=10_000,
            d_loop=60_000,
        ),
        straight_factory=s_f_dbu,
        bend90_cell=bend,
    )

    return c


@kf.cell
def gc_loopback(width: float) -> kf.KCell:
    c = kf.KCell()
    gcs = [
        c
        << grating_coupler_elliptical_te(
            wg_width=width,
        )
        for _ in range(4)
    ]
    for i in range(4):
        gc = gcs[i]
        gc.rotate(3)
        gc.movex(50_000 * i)

    b = kf.cells.circular.bend_circular(width=width, radius=10, layer=LAYER.WG)
    kf.routing.optical.place90(
        c,
        gcs[0].ports["o1"],
        gcs[3].ports["o1"],
        kf.routing.optical.route_loopback(
            gcs[0].ports["o1"],
            gcs[3].ports["o1"],
            bend90_radius=10_000,
            # bend180_radius=10_000,
            d_loop=60_000,
        ),
        straight_factory=s_f_dbu,
        bend90_cell=b,
    )

    c.add_port(name="o1", port=gcs[1].ports["o1"])
    c.add_port(name="o2", port=gcs[2].ports["o1"])
    c.add_port(name="ALIGN_IN", port=gcs[0].ports["FL"])
    c.add_port(name="ALIGN_OUT", port=gcs[3].ports["FL"])
    c.add_port(name="IN", port=gcs[1].ports["FL"])
    c.add_port(name="OUT", port=gcs[2].ports["FL"])

    return c


@kf.cell()
def cutback_rib(width: float, length: float) -> kf.KCell:
    c = kf.KCell()

    b = kf.cells.circular.bend_circular(
        width=width, radius=10, layer=LAYER.WG, enclosure=rib_enc
    )
    radius = 10
    slab = 1
    spacing = 1 + slab + width
    _length = length / 50

    s_f = partial(
        kf.cells.straight.straight, width=width, layer=LAYER.WG, enclosure=rib_enc
    )

    b_inners = [c << b for _ in range(4)]
    b_inners[1].connect("o2", b_inners[0], "o2")
    b_inners[2].connect("o1", b_inners[1], "o1", mirror=True)
    s_space = c << s_f(length=spacing)
    s_space.connect("o1", b_inners[2], "o2")
    b_inners[3].connect("o1", s_space, "o2")
    l0_2 = c << s_f(length=_length + 2 * radius + spacing)
    l0_2.connect("o1", b_inners[3], "o2")
    p2 = l0_2.ports["o2"]

    if length > 0:
        l0_1 = c << s_f(length=_length)
        l0_1.connect("o1", b_inners[0], "o1")
        p1 = l0_1.ports["o2"].copy()
        p1.mirror = not p1.mirror
    else:
        p1 = b_inners[0].ports["o1"]
        p1.mirror = not p1.mirror

    for i in range(12):
        bends = [c << b for _ in range(8)]
        bends[0].connect("o1", p1)
        bends[1].connect("o1", p2)
        v1 = c << s_f(length=spacing * (1 + 4 * i))
        v1.connect("o1", bends[0], "o2")
        v2 = c << s_f(length=spacing * (3 + 4 * i))
        v2.connect("o1", bends[1], "o2")
        bends[2].connect("o1", v1, "o2")
        bends[3].connect("o1", v2, "o2")
        h1 = c << s_f(length=_length + 2 * radius + spacing * (1 + 4 * i))
        h2 = c << s_f(length=_length + 2 * radius + spacing * (3 + 4 * i))
        h1.connect("o1", bends[2], "o2")
        h2.connect("o1", bends[3], "o2")
        bends[4].connect("o1", h1, "o2")
        bends[5].connect("o1", h2, "o2")
        v3 = c << s_f(length=spacing * (3 + 4 * i))
        v4 = c << s_f(length=spacing * (5 + 4 * i))
        v3.connect("o1", bends[4], "o2")
        v4.connect("o1", bends[5], "o2")
        bends[6].connect("o1", v3, "o2")
        bends[7].connect("o1", v4, "o2")
        h3 = c << s_f(length=_length + 2 * radius + spacing * (3 + 4 * i))
        h4 = c << s_f(length=_length + 2 * radius + spacing * (5 + 4 * i))
        h3.connect("o1", bends[6], "o2")
        h4.connect("o1", bends[7], "o2")

        p1 = h3.ports["o2"]
        p2 = h4.ports["o2"]

    c.add_port(name="o1", port=p1)
    c.add_port(name="o2", port=p2)
    return c


@kf.cell()
def cutback_ridge(width: float, length: float) -> kf.KCell:
    c = kf.KCell()

    b = kf.cells.circular.bend_circular(
        width=width, radius=10, layer=LAYER.WG, enclosure=ridge_enc
    )
    radius = 10
    slab = 1
    spacing = 1 + slab + width
    _length = length / 50

    s_f = partial(
        kf.cells.straight.straight, width=width, layer=LAYER.WG, enclosure=ridge_enc
    )

    b_inners = [c << b for _ in range(4)]
    b_inners[1].connect("o2", b_inners[0], "o2")
    b_inners[2].connect("o1", b_inners[1], "o1", mirror=True)
    s_space = c << s_f(length=spacing)
    s_space.connect("o1", b_inners[2], "o2")
    b_inners[3].connect("o1", s_space, "o2")
    l0_2 = c << s_f(length=_length + 2 * radius + spacing)
    l0_2.connect("o1", b_inners[3], "o2")
    p2 = l0_2.ports["o2"]

    if length > 0:
        l0_1 = c << s_f(length=_length)
        l0_1.connect("o1", b_inners[0], "o1")
        p1 = l0_1.ports["o2"].copy()
        p1.mirror = not p1.mirror
    else:
        p1 = b_inners[0].ports["o1"]
        p1.mirror = not p1.mirror

    for i in range(12):
        bends = [c << b for _ in range(8)]
        bends[0].connect("o1", p1)
        bends[1].connect("o1", p2)
        v1 = c << s_f(length=spacing * (1 + 4 * i))
        v1.connect("o1", bends[0], "o2")
        v2 = c << s_f(length=spacing * (3 + 4 * i))
        v2.connect("o1", bends[1], "o2")
        bends[2].connect("o1", v1, "o2")
        bends[3].connect("o1", v2, "o2")
        h1 = c << s_f(length=_length + 2 * radius + spacing * (1 + 4 * i))
        h2 = c << s_f(length=_length + 2 * radius + spacing * (3 + 4 * i))
        h1.connect("o1", bends[2], "o2")
        h2.connect("o1", bends[3], "o2")
        bends[4].connect("o1", h1, "o2")
        bends[5].connect("o1", h2, "o2")
        v3 = c << s_f(length=spacing * (3 + 4 * i))
        v4 = c << s_f(length=spacing * (5 + 4 * i))
        v3.connect("o1", bends[4], "o2")
        v4.connect("o1", bends[5], "o2")
        bends[6].connect("o1", v3, "o2")
        bends[7].connect("o1", v4, "o2")
        h3 = c << s_f(length=_length + 2 * radius + spacing * (3 + 4 * i))
        h4 = c << s_f(length=_length + 2 * radius + spacing * (5 + 4 * i))
        h3.connect("o1", bends[6], "o2")
        h4.connect("o1", bends[7], "o2")

        p1 = h3.ports["o2"]
        p2 = h4.ports["o2"]

    c.add_port(name="o1", port=p1)
    c.add_port(name="o2", port=p2)

    return c


@kf.cell
def RibLoss() -> kf.KCell:
    c = kf.KCell()

    # pos = kf.kdb.Point(0, 0)
    pos = (0, 0)
    for i, d in enumerate(
        [
            {"width": 0.3, "length": 0},
            {"width": 0.3, "length": 25_000},
            {"width": 0.3, "length": 5_000},
            {"width": 0.3, "length": 20_000},
            {"width": 0.3, "length": 10_000},
            {"width": 0.3, "length": 15_000},
            {"width": 0.5, "length": 0},
            {"width": 0.5, "length": 25_000},
            {"width": 0.5, "length": 5_000},
            {"width": 0.5, "length": 20_000},
            {"width": 0.5, "length": 10_000},
            {"width": 0.5, "length": 15_000},
            {"width": 0.8, "length": 0},
            {"width": 0.8, "length": 25_000},
            {"width": 0.8, "length": 5_000},
            {"width": 0.8, "length": 20_000},
            {"width": 0.8, "length": 10_000},
            {"width": 0.8, "length": 15_000},
        ]
    ):
        rib = c << cutback_rib_assembled(bool(i % 2), **d)
        if i % 2:
            rib.move((rib.xmin, rib.ymin), pos)
            pos = (0, rib.ymax + 10_000)
        else:
            rib.move((rib.xmin, rib.ymin), pos)
            pos = (rib.xmax + 10_000, pos[1])
        c.add_ports(
            filter(lambda port: port.port_type == "fiber_launch", rib.ports),
            prefix=rib.name + "_",
        )

    c.shapes(LAYER.BORDER).insert(c.bbox().enlarged(10_000))

    return c


@kf.cell
def RidgeLoss() -> kf.KCell:
    c = kf.KCell()

    # pos = kf.kdb.Point(0, 0)
    pos = (0, 0)
    for i, d in enumerate(
        [
            {"width": 0.3, "length": 0},
            {"width": 0.3, "length": 25_000},
            {"width": 0.3, "length": 5_000},
            {"width": 0.3, "length": 20_000},
            {"width": 0.3, "length": 10_000},
            {"width": 0.3, "length": 15_000},
            {"width": 0.5, "length": 0},
            {"width": 0.5, "length": 25_000},
            {"width": 0.5, "length": 5_000},
            {"width": 0.5, "length": 20_000},
            {"width": 0.5, "length": 10_000},
            {"width": 0.5, "length": 15_000},
            {"width": 0.8, "length": 0},
            {"width": 0.8, "length": 25_000},
            {"width": 0.8, "length": 5_000},
            {"width": 0.8, "length": 20_000},
            {"width": 0.8, "length": 10_000},
            {"width": 0.8, "length": 15_000},
        ]
    ):
        rib = c << cutback_ridge_assembled(bool(i % 2), **d)
        if i % 2:
            rib.move((rib.xmin, rib.ymin), pos)
            pos = (0, rib.ymax + 10_000)
        else:
            rib.move((rib.xmin, rib.ymin), pos)
            pos = (rib.xmax + 10_000, pos[1])
        c.add_ports(
            filter(lambda port: port.port_type == "fiber_launch", rib.ports),
            prefix=rib.name + "_",
        )

    c.shapes(LAYER.BORDER).insert(c.bbox().enlarged(10_000))

    return c


@kf.cell
def cutback_rib_assembled(mirror: bool = False, **cutback_kwargs):
    c = kf.KCell()
    s_f = partial(kf.cells.straight.straight_dbu, layer=LAYER.WG, enclosure=rib_enc)
    b = kf.cells.circular.bend_circular(
        width=cutback_kwargs["width"],
        radius=10,
        layer=LAYER.WG,
        enclosure=kf.LayerEnclosure(
            sections=[(LAYER.WGCLAD, 500)],
            name="RIB",
            main_layer=LAYER.WG,
            kcl=kf.kcl,
        ),
    )
    rib = c << cutback_rib(**cutback_kwargs)
    gca = c << gc_loopback(width=cutback_kwargs["width"])
    if mirror:
        rib.trans = kf.kdb.Trans(2, True, 0, 0)
        rib.move((rib.xmax, rib.ymin), (gca.xmin - 10_000, gca.ymin))

        kf.routing.optical.route(
            c,
            rib.ports["o2"],
            gca.ports["o1"],
            straight_factory=s_f,
            bend90_cell=b,
            end_straight=10_000,
        )
        kf.routing.optical.route(
            c,
            rib.ports["o1"],
            gca.ports["o2"],
            straight_factory=s_f,
            bend90_cell=b,
            end_straight=12_000,
        )
    else:
        rib.move((rib.xmin, rib.ymin), (gca.xmax + 10_000, gca.ymin))
        kf.routing.optical.route(
            c,
            rib.ports["o2"],
            gca.ports["o2"],
            straight_factory=s_f,
            bend90_cell=b,
            end_straight=10_000,
        )
        kf.routing.optical.route(
            c,
            rib.ports["o1"],
            gca.ports["o1"],
            straight_factory=s_f,
            bend90_cell=b,
            end_straight=12_000,
        )
    c.add_ports(
        filter(lambda port: port.port_type == "fiber_launch", gca.ports),
        prefix=rib.name + "_",
    )
    return c


@kf.cell
def cutback_ridge_assembled(mirror: bool = False, **cutback_kwargs):
    c = kf.KCell()
    s_f = partial(kf.cells.straight.straight_dbu, layer=LAYER.WG)
    b = kf.cells.circular.bend_circular(
        width=cutback_kwargs["width"],
        radius=10,
        layer=LAYER.WG,
    )
    ridge = c << cutback_ridge(**cutback_kwargs)
    gca = c << gc_loopback(width=cutback_kwargs["width"])
    if mirror:
        ridge.trans = kf.kdb.Trans(2, True, 0, 0)
        ridge.move((ridge.xmax, ridge.ymin), (gca.xmin - 10_000, gca.ymin))

        kf.routing.optical.route(
            c,
            ridge.ports["o2"],
            gca.ports["o1"],
            straight_factory=s_f,
            bend90_cell=b,
            end_straight=10_000,
        )
        kf.routing.optical.route(
            c,
            ridge.ports["o1"],
            gca.ports["o2"],
            straight_factory=s_f,
            bend90_cell=b,
            end_straight=12_000,
        )
    else:
        ridge.move((ridge.xmin, ridge.ymin), (gca.xmax + 10_000, gca.ymin))
        kf.routing.optical.route(
            c,
            ridge.ports["o2"],
            gca.ports["o2"],
            straight_factory=s_f,
            bend90_cell=b,
            end_straight=10_000,
        )
        kf.routing.optical.route(
            c,
            ridge.ports["o1"],
            gca.ports["o1"],
            straight_factory=s_f,
            bend90_cell=b,
            end_straight=12_000,
        )
    c.add_ports(
        filter(lambda port: port.port_type == "fiber_launch", gca.ports),
        prefix=ridge.name + "_",
    )
    return c


@kf.cell
def TOP() -> kf.KCell:
    c = kf.KCell()

    c1 = c << RibLoss()
    c2 = c << RidgeLoss()

    c1.dmove((6450, 200))
    c2.dmove((4200, 4500))

    c.shapes(LAYER.BORDER).insert(kf.kdb.DBox(0, 0, 10_000, 10_000))

    # c1 = c << CHIPLET1()
    # c2 = c << CHIPLET2()
    # c2.movey(c2.bbox().bottom, c1.bbox().top + 10_000)

    return c


@kf.cell
def grating_coupler_elliptical(
    polarization: Literal["te"] | Literal["tm"] = "te",
    taper_length: float = 20,
    taper_angle: float = 40,
    trenches_extra_angle: float = 10,
    lambda_c: float = 1.5,
    fiber_angle: float = 15,
    grating_line_width: float = 0.250,
    wg_width: float = 0.5,
    neff: float = 2.6,  # tooth effective index
    layer_taper: kf.kdb.LayerInfo | None = LAYER.WG,
    layer_trench: kf.kdb.LayerInfo = LAYER.SHALLOW_ETCH,
    p_start: int = 26,
    n_periods: int = 30,
    taper_offset: int = 0,
    taper_extent_n_periods: float | Literal["first"] | Literal["last"] = "last",
    period: int | None = None,
    x_fiber_launch: int | None = None,
    clad_index: float = 1.4,  # cladding index
) -> kf.KCell:
    DEG2RAD = np.pi / 180
    sthc = np.sin(fiber_angle * DEG2RAD)

    if period is not None:
        neff = lambda_c / period + clad_index * sthc

    d = neff**2 - clad_index**2 * sthc**2
    a1 = lambda_c * neff / d
    b1 = lambda_c / np.sqrt(d)
    x1 = lambda_c * clad_index * sthc / d

    _period = a1 + x1

    trench_line_width = _period - grating_line_width

    c = kf.KCell()
    c.info["polarization"] = polarization
    c.info["wavelength"] = lambda_c * 1e3

    # Make each grating line

    for p in range(p_start, p_start + n_periods + 2):
        tooth = grating_tooth(
            (p - 0.5) * a1,
            (p - 0.5) * b1,
            (p - 0.5) * x1,
            trench_line_width,
            taper_angle + trenches_extra_angle,
        )
        c.shapes(layer_trench).insert(tooth)
    kf.kdb.Region(c.shapes(layer_trench))

    # Make the taper
    if taper_extent_n_periods == "last":
        n_periods_over_grating: float = n_periods + 1
    elif taper_extent_n_periods == "first":
        n_periods_over_grating = -1.5
    else:
        n_periods_over_grating = taper_extent_n_periods

    def _get_taper_pts(
        n_periods_over_grating: float,
    ) -> tuple[list[kf.kdb.DPoint], float]:
        p_taper = p_start + n_periods_over_grating
        _taper_length = taper_length + (n_periods_over_grating - 1) * _period

        a_taper = a1 * p_taper
        b_taper = b1 * p_taper
        x_taper = x1 * p_taper

        x_output = a_taper + x_taper - _taper_length + grating_line_width / 2
        taper_pts = grating_taper_points(
            a_taper,
            b_taper,
            x_output,
            x_taper + _period,
            taper_angle,
            wg_width=wg_width,
        )
        return taper_pts, x_output

    taper_pts, x_output = _get_taper_pts(n_periods_over_grating=n_periods_over_grating)
    if layer_taper is not None:
        c.shapes(layer_taper).insert(
            kf.kdb.DPolygon(taper_pts).transformed(kf.kdb.DTrans(taper_offset, 0))
        )
        c.create_port(
            name="o1",
            trans=kf.kdb.Trans.R180,
            width=int(wg_width / c.kcl.dbu),
            layer_info=layer_taper,
        )

    c.transform(kf.kdb.Trans(int(-x_output - taper_offset), 0))

    # Add port
    c.info["period"] = _period

    # Add GC Fibre launch reference port, we are putting it at the same place
    # as the other I/O port for now
    x0 = p_start * a1 - grating_line_width + 9

    x_fiber_launch = x0 if x_fiber_launch is None else x_fiber_launch
    c.create_port(
        name="FL",
        trans=kf.kdb.Trans(x_fiber_launch, 0),
        layer_info=LAYER.FIBER_LAUNCH,
        width=100,
        port_type="fiber_launch",
    )
    y0 = 0
    c.info.p0_overclad_x0 = x0
    c.info.p0_overclad_y0 = y0
    return c


def grating_tooth(
    ap: float,
    bp: float,
    xp: int,
    width: int,
    taper_angle: float,
    spiked: bool = True,
    angle_step: float = 1.0,
) -> kf.kdb.Region:
    angle_min = -taper_angle / 2
    angle_max = taper_angle / 2

    backbone_points = ellipse_arc(ap, bp, xp, angle_min, angle_max, angle_step)
    return (
        _extracted_from_grating_tooth_15(width, backbone_points)
        if spiked
        else kf.kdb.Region(kf.kdb.Path(backbone_points, width))
    )


def _extracted_from_grating_tooth_15(width, backbone_points):
    spike_length = width // 3
    path = kf.kdb.DPath(backbone_points, width).polygon()
    edges = kf.kdb.Edges([path.to_itype(kf.kcl.dbu)])
    bb_edges = kf.kdb.Edges(
        [
            kf.kdb.DEdge(backbone_points[0], backbone_points[1]).to_itype(kf.kcl.dbu),
            kf.kdb.DEdge(backbone_points[-1], backbone_points[-2]).to_itype(kf.kcl.dbu),
        ]
    )
    border_edges = edges.interacting(bb_edges)
    result = kf.kdb.Region([path.to_itype(kf.kcl.dbu)])
    for edge in border_edges.each():
        shifted = edge.shifted(spike_length)
        shifted_center = (shifted.p1 + shifted.p2.to_v()) / 2
        result.insert(kf.kdb.Polygon([edge.p1, shifted_center, edge.p2]))
    result.merge()

    return result


def grating_taper_points(
    a: float,
    b: float,
    x0: int,
    taper_length: float,
    taper_angle: float,
    wg_width: float,
    angle_step: float = 1.0,
) -> list[kf.kdb.DPoint]:
    taper_arc = ellipse_arc(
        a, b, taper_length, -taper_angle / 2, taper_angle / 2, angle_step=angle_step
    )

    p0 = kf.kdb.DPoint(x0, wg_width / 2)
    p1 = kf.kdb.DPoint(x0, -wg_width / 2)
    return [p0, p1] + taper_arc


def ellipse_arc(
    a: float,
    b: float,
    x0: float,
    angle_min: float,
    angle_max: float,
    angle_step: float = 0.5,
) -> list[kf.kdb.DPoint]:
    angle = np.arange(angle_min, angle_max + angle_step, angle_step) * np.pi / 180
    xs = a * np.cos(angle) + x0
    ys = b * np.sin(angle)
    return [
        kf.kdb.DPoint(x, y) for x, y in zip(xs, ys, strict=False)
    ]  # np.column_stack([xs, ys])


grating_coupler_elliptical_te = partial(
    grating_coupler_elliptical,
    polarization="te",
    taper_length=20,
    taper_angle=40,
    lambda_c=1.5,
    fiber_angle=15,
    grating_line_width=0.250,
    wg_width=0.500,
    p_start=26,
    n_periods=30,
    taper_offset=1.776,
    x_fiber_launch=None,
)

if __name__ == "__main__":
    c = TOP()
    c.write("test_chip.gds")
    c.show()

    # kf.kcl.read("test_chip.gds")
    # c = kf.kcl["TOP"]
    rib = c.kcl["RibLoss"]
    ridge = c.kcl["RidgeLoss"]

    import csv

    with open("design_manifest.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "cell",
                "x",
                "y",
                "width",
                "length",
                "analysis",
                "analysis_parameters",
            ]
        )

        rib_it = rib.kdb_cell.begin_instances_rec()
        rib_it.targets = "cutback_rib*"
        while not rib_it.at_end():
            _c = c.kcl[rib_it.inst_cell().cell_index()]
            _disp = (rib_it.trans() * rib_it.inst_trans()).disp
            writer.writerow(
                [
                    _c.name,
                    _disp.x,
                    _disp.y,
                    _c.settings["width"],
                    _c.settings["length"],
                    "[power_envelope]",
                    '[{"n": 10, "wvl_of_interest_nm": 1550}]',
                ]
            )
            rib_it.next()
        ridge_it = ridge.kdb_cell.begin_instances_rec()
        ridge_it.targets = "cutback_ridge*"
        while not ridge_it.at_end():
            _c = c.kcl[ridge_it.inst_cell().cell_index()]
            _disp = (ridge_it.trans() * ridge_it.inst_trans()).disp
            writer.writerow(
                [
                    _c.name,
                    _disp.x,
                    _disp.y,
                    _c.settings["width"],
                    _c.settings["length"],
                    "[power_envelope]",
                    '[{"n": 10, "wvl_of_interest_nm": 1550}]',
                ]
            )
            ridge_it.next()
        rib_it = rib.kdb_cell.begin_instances_rec()

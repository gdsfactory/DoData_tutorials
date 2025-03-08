"""Generates a layout for a chip with a ring sweep."""

from functools import partial

import gdsfactory as gf

size = (6050, 4100)
pack = partial(gf.pack, max_size=size, add_ports_prefix=False, spacing=2)
add_gc = gf.routing.add_fiber_array
ring_double = gf.components.ring_double
length_x = 0.1


@gf.cell(set_name=False)
def ring_with_gc(
    radius: float = 10.0, gap: float = 0.2, length_x: float = 0.1
) -> gf.Component:
    """Returns a ring with a grating coupler."""
    ring = gf.components.ring_double(radius=radius, gap=gap, length_x=length_x)
    ring_with_gc = add_gc(ring)
    ring_with_gc.name = f"RingDouble-{radius}-{gap}-"
    return ring_with_gc


@gf.cell(check_ports=False)
def rings() -> gf.Component:
    """Returns a component ring sweep."""
    gaps = [100, 150, 200]
    radiuses = [10]

    rings = [
        ring_with_gc(
            radius=radius,
            length_x=length_x,
            gap=gap * 1e-3,
        )
        for radius in radiuses
        for gap in gaps
    ]
    gaps = [150, 200, 250]
    radiuses = [20]
    rings += [
        ring_with_gc(
            radius=radius,
            length_x=length_x,
            gap=gap * 1e-3,
        )
        for radius in radiuses
        for gap in gaps
    ]

    gaps = [100, 150, 200]
    radiuses = [5]
    rings += [
        ring_with_gc(
            radius=radius,
            length_x=length_x,
            gap=gap * 1e-3,
        )
        for radius in radiuses
        for gap in gaps
    ]

    # rings = [c.flatten() for c in rings]
    c = pack(rings)
    if len(c) > 1:
        raise ValueError(f"Failed to pack in 1 component of {size}, got {len(c)}")
    return c[0]


@gf.cell(check_ports=False)
def top() -> gf.Component:
    """Returns a top cell."""
    c = pack([rings])
    if len(c) > 1:
        raise ValueError(f"Failed to pack in 1 component of {size}, got {len(c)}")
    return c[0]


if __name__ == "__main__":
    c = top()
    c.write_gds("test_chip.gds")
    c.show()

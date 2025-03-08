"""Generate a layout with a resistor sweep."""

from functools import partial

import gdsfactory as gf

size = (6050, 4100)
pack = partial(gf.pack, max_size=size, add_ports_prefix=False, spacing=2)
add_gc = gf.routing.add_fiber_array
length_x = 0.1


@gf.cell
def resistance_sheet(width=10) -> gf.Component:
    """Resistor sheet."""
    c = gf.components.resistance_sheet(
        width=width,
    )
    return c


@gf.cell
def resistance() -> gf.Component:
    """Resistor sweep."""
    widths = [10, 20, 100]
    sweep = [
        resistance_sheet(
            width=width,
        )
        for width in widths
    ]
    return gf.grid(sweep, shape=(len(sweep), 1))


@gf.cell
def top() -> gf.Component:
    """Top cell."""
    c = pack([resistance])
    if len(c) > 1:
        raise ValueError(f"Failed to pack in 1 component of {size}, got {len(c)}")
    return c[0]


if __name__ == "__main__":
    c = top()
    c.write_gds("test_chip.gds")
    c.show()

"""Generate a test DXF file with various entities for testing."""
import ezdxf
from ezdxf import units

doc = ezdxf.new('R2010')
doc.units = units.MM
msp = doc.modelspace()

# Layer definitions
doc.layers.add('OUTLINE', color=1)      # red
doc.layers.add('HOLES', color=4)        # cyan
doc.layers.add('POCKETS', color=3)      # green
doc.layers.add('MOUNTS', color=5)       # blue
doc.layers.add('TEXT', color=7)         # white

# --- OUTLINE layer: main rectangular plate ---
msp.add_lwpolyline([
    (0, 0), (200, 0), (200, 150), (0, 150)
], dxfattribs={'layer': 'OUTLINE'}).closed = True

# inner cutout
msp.add_lwpolyline([
    (20, 20), (180, 20), (180, 130), (20, 130)
], dxfattribs={'layer': 'OUTLINE'}).closed = True

# --- HOLES layer: 4 mounting holes ---
for cx, cy in [(30, 30), (170, 30), (30, 120), (170, 120)]:
    msp.add_circle((cx, cy), radius=5, dxfattribs={'layer': 'HOLES'})

# --- POCKETS layer: 2 rectangular pockets ---
msp.add_lwpolyline([
    (50, 50), (80, 50), (80, 100), (50, 100)
], dxfattribs={'layer': 'POCKETS'}).closed = True

msp.add_lwpolyline([
    (120, 50), (150, 50), (150, 100), (120, 100)
], dxfattribs={'layer': 'POCKETS'}).closed = True

# --- MOUNTS layer: 2 large circular features ---
msp.add_circle((100, 75), radius=25, dxfattribs={'layer': 'MOUNTS'})
msp.add_circle((100, 75), radius=15, dxfattribs={'layer': 'MOUNTS'})

# --- TEXT layer: annotations ---
t1 = msp.add_text("TEST PLATE - CAD Analyzer Demo",
             dxfattribs={'layer': 'TEXT', 'height': 6})
t1.dxf.insert = (40, 160)

# bottom-left detail text
t2 = msp.add_text("Material: Aluminum 6061\nThickness: 10mm\nScale: 1:1",
             dxfattribs={'layer': 'TEXT', 'height': 4})
t2.dxf.insert = (5, -15)

# center line
msp.add_line((100, -5), (100, 155), dxfattribs={'layer': 'TEXT'})

doc.saveas('D:/cad-analyzer/test_plate.dxf')
print("Test DXF saved: D:/cad-analyzer/test_plate.dxf")
print("Layers: OUTLINE, HOLES, POCKETS, MOUNTS, TEXT")

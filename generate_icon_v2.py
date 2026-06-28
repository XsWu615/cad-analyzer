"""Generate CAD Analyzer icon using PyVista 3D rendering."""

import pyvista as pv
import numpy as np
from PIL import Image, ImageDraw

pv.OFF_SCREEN = True
pv.global_theme.anti_aliasing = 'msaa'

SIZE = 1024
EXPORT_SIZE = 256
R = 1.0
extend = 0.35

plotter = pv.Plotter(window_size=[SIZE, SIZE], off_screen=True)
plotter.set_background('#1e1e1e')

# --- Cube body ---
cube = pv.Cube(center=(0, 0, 0), x_length=2*R, y_length=2*R, z_length=2*R)
plotter.add_mesh(
    cube, color='#0078d4', opacity=0.30,
    show_edges=True, edge_color='#4ecdc4', line_width=3,
    pbr=False, metallic=0.1, roughness=0.8,
)

# --- Grid lines on top face ---
n = 6
for i in range(n + 1):
    t = -R + i * (2 * R) / n
    # horizontal (along X)
    h_line = pv.Line(pointa=(R, t, R + 0.002), pointb=(-R, t, R + 0.002))
    plotter.add_mesh(h_line, color='#4ecdc4', line_width=1, opacity=0.55)
    # vertical (along Y)
    v_line = pv.Line(pointa=(t, R, R + 0.002), pointb=(t, -R, R + 0.002))
    plotter.add_mesh(v_line, color='#4ecdc4', line_width=1, opacity=0.55)

# --- Grid lines on front-right face ---
for i in range(n + 1):
    t = -R + i * (2 * R) / n
    h_line = pv.Line(pointa=(R, t, -R), pointb=(R, t, R))
    plotter.add_mesh(h_line, color='#4ecdc4', line_width=1, opacity=0.35)
for i in range(n + 1):
    t = -R + i * (2 * R) / n
    v_line = pv.Line(pointa=(R, -R, t), pointb=(R, R, t))
    plotter.add_mesh(v_line, color='#4ecdc4', line_width=1, opacity=0.35)

# --- Grid lines on front-left face ---
for i in range(n + 1):
    t = -R + i * (2 * R) / n
    h_line = pv.Line(pointa=(-R, t, -R), pointb=(-R, t, R))
    plotter.add_mesh(h_line, color='#4ecdc4', line_width=1, opacity=0.25)
for i in range(n + 1):
    t = -R + i * (2 * R) / n
    v_line = pv.Line(pointa=(-R, -R, t), pointb=(-R, R, t))
    plotter.add_mesh(v_line, color='#4ecdc4', line_width=1, opacity=0.25)

# --- Construction line extensions from vertices ---
corners_3d = [
    (-R, -R, -R), (R, -R, -R), (-R, R, -R), (R, R, -R),
    (-R, -R,  R), (R, -R,  R), (-R, R,  R), (R, R,  R),
]
for cx, cy, cz in corners_3d:
    ext = pv.Line(pointa=(cx, cy, cz), pointb=(cx, cy, cz - extend))
    plotter.add_mesh(ext, color='#ffffff', line_width=1, opacity=0.25)

# --- Vertex dots ---
for cx, cy, cz in corners_3d:
    s = pv.Sphere(radius=0.04, center=(cx, cy, cz))
    plotter.add_mesh(s, color='#ffffff', pbr=False)

# --- Camera: isometric projection ---
dist = 4.5
plotter.camera.position = (dist, dist, dist * 0.85)
plotter.camera.focal_point = (0, 0, 0.1)
plotter.camera.up = (0, 0, 1)
plotter.camera.zoom(1.25)

# --- Lighting ---
plotter.add_light(pv.Light(position=(3, 3, 8), color='#ffffff', intensity=0.6))
plotter.add_light(pv.Light(position=(-3, -2, -2), color='#4ecdc4', intensity=0.2))

# --- Render ---
plotter.show(auto_close=False)
img_array = plotter.screenshot(transparent_background=False, return_img=True)
plotter.close()

# Convert to PIL and process
img = Image.fromarray(img_array)
img = img.resize((EXPORT_SIZE, EXPORT_SIZE), Image.LANCZOS)

# Rounded corners
mask = Image.new('L', (EXPORT_SIZE, EXPORT_SIZE), 0)
draw = ImageDraw.Draw(mask)
draw.rounded_rectangle([0, 0, EXPORT_SIZE - 1, EXPORT_SIZE - 1], 28, fill=255)

result = Image.new('RGBA', (EXPORT_SIZE, EXPORT_SIZE), (0, 0, 0, 0))
result.paste(img, mask=mask)

result.save('D:/cad-analyzer/icon.png')

# Multi-res ICO — save each size to temp PNGs, combine with PIL
import io, struct
sizes = [256, 128, 64, 48, 32, 24, 16]
png_buffers = []
for s in sizes:
    frame = result.resize((s, s), Image.LANCZOS)
    buf = io.BytesIO()
    frame.save(buf, format='PNG')
    png_buffers.append(buf.getvalue())

# Write ICO manually for reliable multi-res support
with open('D:/cad-analyzer/icon.ico', 'wb') as f:
    # ICO header
    f.write(struct.pack('<HHH', 0, 1, len(sizes)))  # reserved, type=ico, count
    # Image directory entries
    offset = 6 + 16 * len(sizes)  # header + directory
    entries = []
    for s, png_data in zip(sizes, png_buffers):
        data_len = len(png_data)
        entries.append((s if s < 256 else 0, s if s < 256 else 0, 0, 0, 32, data_len, offset))
        offset += data_len
    for w, h, colors, planes, bpp, data_len, off in entries:
        f.write(struct.pack('<BBBBHHII', w, h, colors, planes, 1, bpp, data_len, off))
    # Image data
    for png_data in png_buffers:
        f.write(png_data)

print("Icon saved: D:/cad-analyzer/icon.png (256x256)")
print("Icon saved: D:/cad-analyzer/icon.ico (multi-res)")

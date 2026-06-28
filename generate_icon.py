"""Generate CAD Analyzer app icon — Structural Void philosophy."""

from PIL import Image, ImageDraw
import math

SIZE = 256
MARGIN = 32
CENTER = SIZE / 2

# Colors
BG = (0x1e, 0x1e, 0x1e)
CYAN = (0x4e, 0xcd, 0xc4)
BLUE = (0x00, 0x78, 0xd4)
WHITE = (0xcc, 0xcc, 0xcc)
CYAN_DIM = (0x2a, 0x80, 0x78)
BLUE_DIM = (0x00, 0x3d, 0x6b)
GRID_LINE = (0x33, 0x33, 0x33)
CORNER_RADIUS = 28

# Isometric cube geometry (center-origin)
# Three visible faces: top, left, right
# Isometric angles: 30° from horizontal

iso_angle = math.radians(30)
cos_a = math.cos(iso_angle)
sin_a = math.sin(iso_angle)

CUBE_R = 85  # half-edge in isometric projection space

# Cube vertices in "isometric space" (3D → 2D projection)
# Center at (0,0), then translate
# X axis → right-down (dx=cos_a, dy=sin_a)
# Y axis → left-down  (-cos_a, dy=sin_a)
# Z axis → straight up (0, -1)

def project(x, y, z):
    px = CENTER + (x - y) * cos_a
    py = CENTER + (x + y) * sin_a - z
    return (px, py)

# Cube 8 corners: front-bottom-left, front-bottom-right, front-top-left, front-top-right,
#                back-bottom-left,  back-bottom-right,  back-top-left,  back-top-right
# Using x,y,z coordinates where cube is centered:
R = 65  # half-edge length in world space

# Vertices in 3D world space
corners = {
    'fbl': (-R, -R, -R),  # front-bottom-left
    'fbr': ( R, -R, -R),  # front-bottom-right
    'ftl': (-R, -R,  R),  # front-top-left
    'ftr': ( R, -R,  R),  # front-top-right
    'bbl': (-R,  R, -R),  # back-bottom-left
    'bbr': ( R,  R, -R),  # back-bottom-right
    'btl': (-R,  R,  R),  # back-top-left
    'btr': ( R,  R,  R),  # back-top-right
}

pts = {k: project(*v) for k, v in corners.items()}

# Face definitions: list of (corner_names, fill_color)
faces = [
    (['fbl', 'fbr', 'bbr', 'bbl'], BLUE_DIM),   # bottom face
    (['fbl', 'ftl', 'btl', 'bbl'], CYAN_DIM),    # left face
    (['fbr', 'ftr', 'btr', 'bbr'], CYAN),         # right face
    (['ftl', 'ftr', 'btr', 'btl'], BLUE),         # top face
]

def create_rounded_mask(size, radius):
    """Create a rounded rectangle mask."""
    from PIL import Image
    mask = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius, fill=255)
    return mask


def draw_grid_on_face(draw, corners_2d, fill_color, grid_n=4):
    """Draw blueprint grid lines on a face."""
    if len(corners_2d) != 4:
        return

    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = corners_2d

    # Draw face fill
    draw.polygon(corners_2d, fill=fill_color)

    # Draw grid lines inside the face (bilinear interpolation)
    for i in range(1, grid_n):
        t = i / grid_n
        # interpolate along two pairs of opposite edges
        p_ab = (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)
        p_dc = (x3 + (x2 - x3) * t, y3 + (y2 - y3) * t)
        p_ad = (x0 + (x3 - x0) * t, y0 + (y3 - y0) * t)
        p_bc = (x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)

        color = (0, 0, 0, 40)
        # Only draw inside the face - clip isn't needed if we stay within bounds
        # For transparency, we use a dark line
        draw.line([p_ab, p_dc], fill=GRID_LINE, width=1)
        draw.line([p_ad, p_bc], fill=GRID_LINE, width=1)

    # Draw edge lines
    draw.polygon(corners_2d, outline=CYAN, width=2)


def draw_wireframe_edges(draw, pts):
    """Draw all cube edges as wireframe."""
    edges = [
        # bottom face
        ('fbl', 'fbr'), ('fbr', 'bbr'), ('bbr', 'bbl'), ('bbl', 'fbl'),
        # top face
        ('ftl', 'ftr'), ('ftr', 'btr'), ('btr', 'btl'), ('btl', 'ftl'),
        # verticals
        ('fbl', 'ftl'), ('fbr', 'ftr'), ('bbl', 'btl'), ('bbr', 'btr'),
    ]
    for a, b in edges:
        draw.line([pts[a], pts[b]], fill=WHITE, width=1)


def draw_construction_lines(draw, pts):
    """Extend key edges as construction lines (blueprint feel)."""
    extend = 20
    extensions = [
        ('fbl', 'fbr'),  # extend front-bottom edge
        ('bbl', 'bbr'),  # extend back-bottom edge
        ('fbl', 'ftl'),  # extend front-left vertical
    ]
    for a, b in extensions:
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        length = math.sqrt(dx * dx + dy * dy)
        if length > 0:
            dx, dy = dx / length * extend, dy / length * extend
            # extend beyond b
            ex, ey = bx + dx, by + dy
            draw.line([(bx, by), (ex, ey)], fill=WHITE + (80,), width=1)
            # extend beyond a
            ex, ey = ax - dx, ay - dy
            draw.line([(ax, ay), (ex, ey)], fill=WHITE + (80,), width=1)


def draw_vertex_dots(draw, pts):
    """Small highlighted dots at cube vertices."""
    for p in pts.values():
        x, y = p
        draw.ellipse([x-2, y-2, x+2, y+2], fill=WHITE)


def main():
    img = Image.new('RGBA', (SIZE, SIZE), BG)
    draw = ImageDraw.Draw(img)

    # Draw subtle background grid (blueprint paper feel)
    grid_spacing = 16
    for i in range(0, SIZE + grid_spacing, grid_spacing):
        draw.line([(i, 0), (i, SIZE)], fill=(0x2a, 0x2a, 0x2a), width=1)
        draw.line([(0, i), (SIZE, i)], fill=(0x2a, 0x2a, 0x2a), width=1)

    # Draw crosshair center lines
    draw.line([(CENTER, 0), (CENTER, SIZE)], fill=(0x3a, 0x3a, 0x3a), width=1)
    draw.line([(0, CENTER), (SIZE, CENTER)], fill=(0x3a, 0x3a, 0x3a), width=1)

    # Draw the 3D cube
    # Order: back/lower faces first, then front/upper faces
    # 1. Bottom face (back-bottom)
    draw_grid_on_face(draw, [pts['fbl'], pts['fbr'], pts['bbr'], pts['bbl']], BLUE_DIM, 3)
    # 2. Left face
    draw_grid_on_face(draw, [pts['fbl'], pts['ftl'], pts['btl'], pts['bbl']], CYAN_DIM, 3)
    # 3. Right face (front-right, most visible)
    draw_grid_on_face(draw, [pts['fbr'], pts['ftr'], pts['btr'], pts['bbr']], (*CYAN, 60), 4)
    # 4. Top face
    draw_grid_on_face(draw, [pts['ftl'], pts['ftr'], pts['btr'], pts['btl']], BLUE, 4)

    # Wireframe overlay
    draw_wireframe_edges(draw, pts)

    # Construction line extensions
    draw_construction_lines(draw, pts)

    # Vertex highlights
    draw_vertex_dots(draw, pts)

    # Apply rounded corners mask
    mask = create_rounded_mask(SIZE, CORNER_RADIUS)
    bg_img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    bg_img.paste(img, mask=mask)

    # Also create smaller versions for multi-resolution .ico
    bg_img.save('D:/cad-analyzer/icon.png')
    print("Icon saved: D:/cad-analyzer/icon.png (256x256)")

    # Generate .ico with multiple sizes
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = []
    for s in sizes:
        resized = bg_img.resize((s, s), Image.LANCZOS)
        # Convert to RGBA if not already
        if resized.mode != 'RGBA':
            resized = resized.convert('RGBA')
        images.append(resized)

    images[0].save('D:/cad-analyzer/icon.ico',
                   format='ICO',
                   sizes=[(s, s) for s in sizes],
                   append_images=images[1:])
    print("Icon saved: D:/cad-analyzer/icon.ico (multi-res)")


if __name__ == '__main__':
    main()

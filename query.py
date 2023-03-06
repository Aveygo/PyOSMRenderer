import sqlite3, cairo, marshal, base64, json, math, numpy as np, os, queue, threading
from PIL import Image

def calc_area(minx, maxx, miny, maxy):
    return (maxx - minx) * (maxy - miny)

def should_render(minx, maxx, miny, maxy, zoom):
    """
    Some items are too small to render at certain zoom levels
    eg: bounds 100m^2, should only render when zoom > 14
    """
    area = calc_area(minx, maxx, miny, maxy)

    min_zoom = zoom**2
    if area > min_zoom:
        return False
    
    return True

def intersect(minx1, maxx1, miny1, maxy1, minx2, maxx2, miny2, maxy2):
    """
    Check if two rectangles intersect
    """
    return minx1 <= maxx2 and maxx1 >= minx2 and miny1 <= maxy2 and maxy1 >= miny2

def intersect_and_render(minx1, maxx1, miny1, maxy1, minx2, maxx2, miny2, maxy2, zoom):
    """
    Check if two rectangles intersect and if they should be rendered
    """
    return intersect(minx1, maxx1, miny1, maxy1, minx2, maxx2, miny2, maxy2) and should_render(minx1, maxx1, miny1, maxy1, zoom)

class Query:
    def __init__(self):
        self.conn = sqlite3.connect('map.db')
        self.c = self.conn.cursor()

        self.c.execute('''CREATE VIRTUAL TABLE IF NOT EXISTS main_index USING rtree_i32(id, minx, maxx, miny, maxy, +properties TEXT)''') 
        self.c.execute('''CREATE TABLE IF NOT EXISTS nodes (id INTEGER PRIMARY KEY, list TEXT)''')
        self.conn.commit()

        self.conn.create_function("intersect_and_render", 9, intersect_and_render)
        self.conn.create_function("calc_area", 4, calc_area)

        self.cache = "cache/"
        self.cache_queue = queue.Queue()

        t = threading.Thread(target=self.cache_worker)
        t.start()
    
    def cache_worker(self):
        """
        Save numpy arrays to disk (as jpeg)
        """
        while True:
            item = self.cache_queue.get()
            if item is None:
                break

            numpy_img, path = item
            img = Image.fromarray(numpy_img)
            img.save(path, "JPEG", quality=80)

    def undo_tile_convert(self, x, y, zoom):
        """
        Convert tile coordinates to longitude and latitude
        """
        n = 2.0 ** zoom
        lon_deg = x / n * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
        lat_deg = lat_rad * 180.0 / math.pi
        return lon_deg, lat_deg

    def tile_convert(self, lat, long, zoom):
        """
        Convert a longitude and latitude to tile coordinates
        """
        # Check domain
        if long < -180.0 or long > 180.0 or lat < -90.0 or lat > 90.0:
            return None, None
        
        n = 2.0 ** zoom
        x = (long + 180.0) / 360.0 * n
        y = (1.0 - math.log(math.tan(lat * math.pi / 180.0) + 1.0 / math.cos(lat * math.pi / 180.0)) / math.pi) / 2.0 * n
        return x, y
        
    def query(self, bounds, zoom, limit=1000):
        """
        Retuns list of ids of features that intersect with the bounds AND should be rendered
        """
        self.c.execute('''SELECT * FROM main_index WHERE intersect_and_render(minx, maxx, miny, maxy, ?, ?, ?, ?, ?) AND maxx >= ? AND minx <= ? AND maxy >= ? AND miny <= ?  ORDER BY calc_area(minx, maxx, miny, maxy) DESC LIMIT ?''', (bounds[0], bounds[1], bounds[2], bounds[3], zoom, bounds[0], bounds[1], bounds[2], bounds[3], limit))
        return self.c.fetchall()
    
    def load_nodes(self, feature_id, zoom):
        """
        Load the nodes from the database
        """
        self.c.execute('''SELECT list FROM nodes WHERE id = ?''', (feature_id,))
        data = self.c.fetchone()[0]
        node_list = marshal.loads(base64.b64decode(data))
        nodes = []
        for i in range(0, len(node_list), 2):
            x, y = self.tile_convert(node_list[i], node_list[i+1], zoom)
            nodes.append((x, y))        

        return nodes
    
    def render_tile(self, tile_x, tile_y, zoom, resolution=256):
        """
        Tile rendering, finds all features that intersect with the tile and renders them to a numpy array
        """

        # Bounds are in tile coordinates, so we need to convert them to lat/lon
        lon_min, lat_min = self.undo_tile_convert(tile_x, tile_y, zoom)
        lon_max, lat_max = self.undo_tile_convert(tile_x + 1, tile_y + 1, zoom)

        # We may be "upside down" so swap the bounds if necessary
        if lon_min > lon_max:
            lon_min, lon_max = lon_max, lon_min
        if lat_min > lat_max:
            lat_min, lat_max = lat_max, lat_min

        # Check if image has already been rendered and cached as a numpy array
        path = self.cache + str(zoom) + "_" + str(tile_x) + "_" + str(tile_y) + ".jpg"
        if os.path.exists(path):
            return path
        
        # Create the surface
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, resolution, resolution)
        ctx = cairo.Context(surface)

        # Set the scale
        ctx.scale(resolution / ((tile_x + 1) - tile_x), resolution / ((tile_y + 1) - tile_y))
        ctx.translate(-tile_x, -tile_y)

        # Query the database
        features = self.query([lat_min, lat_max, lon_min, lon_max], zoom)

        # Draw background        
        ctx.set_source_rgba(1, 1, 1, 1)
        back_min_x, back_min_y = self.tile_convert(lat_min, lon_min, zoom)
        back_max_x, back_max_y = self.tile_convert(lat_max, lon_max, zoom)
        ctx.rectangle(back_min_x, back_min_y, back_max_x - back_min_x, back_max_y - back_min_y)
        ctx.fill()

        # Draw features
        for obj in features:
            # Get the nodes and properties
            nodes, props = self.load_nodes(obj[0], zoom), json.loads(obj[5])

            # Set color to black
            ctx.set_source_rgba(0, 0, 0, 1)

            # Change line width if highway
            if props.get("highway", False):
                ctx.set_line_width(0.003)
            else:    
                ctx.set_line_width(0.0015)

            # Draw the nodes
            for i in range(len(nodes)):
                x, y = nodes[i]
                if i == 0:
                    ctx.move_to(x, y)
                else:
                    ctx.line_to(x, y)
            ctx.stroke()
        
        # Load numpy data from surface
        numpy_data = np.frombuffer(surface.get_data(), np.uint8).reshape((surface.get_height(), surface.get_width(), 4))

        # Reorder channels and remove alpha
        numpy_data = numpy_data[:, :, [2, 1, 0]]

        # Add the image to the cache (if zoom < 14)
        if zoom < 14:
            self.cache_queue.put((numpy_data, path))

        # return numpy data
        return numpy_data
        
    def close(self):
        self.conn.close()
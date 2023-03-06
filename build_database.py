import osmium
from osmium.osm import Node, Way
import sqlite3, marshal, base64, json

class Handler(osmium.SimpleHandler):
    def __init__(self):
        osmium.SimpleHandler.__init__(self)

        self.conn = sqlite3.connect('map.db')
        self.c = self.conn.cursor()

        self.c.execute('''CREATE VIRTUAL TABLE IF NOT EXISTS main_index USING rtree(id, minx, maxx, miny, maxy, +properties TEXT)''') 
        self.c.execute('''CREATE TABLE IF NOT EXISTS nodes (id INTEGER PRIMARY KEY, list TEXT)''')
        self.conn.commit()

    def node_pos(self, node: Node) -> tuple[float, float]:
        """
        Get the lat/lon of a node
        """
        return (node.location.lat_without_check(), node.location.lon_without_check())

    def find_bounds(self, nodes:list[Node]):
        """
        Calculate the bounds of a list of nodes, the min/max lat/lon.
        """
        lat, lon = self.node_pos(nodes[0])
        bounds = [lat, lat, lon, lon]
        for node in nodes:
            
            lat, lon = self.node_pos(node)

            # Invalid node (2^31 - 1)
            if lat == 214.7483647 or lon == 214.7483647:
                return None

            if lat < bounds[0]:
                bounds[0] = lat
            
            if lat > bounds[1]:
                bounds[1] = lat
            
            if lon < bounds[2]:
                bounds[2] = lon
            
            if lon > bounds[3]:
                bounds[3] = lon
        
        return bounds

    def dump_nodes(self, nodes:list[Node]):
        """
        Convert list of nodes to a binary representation
        """
        flat_nodes = []
        for node in nodes:
            lat, lon = self.node_pos(node)
            flat_nodes.append(lat)
            flat_nodes.append(lon)

        return base64.b64encode(marshal.dumps(flat_nodes))
    
    def load_nodes(self, data):
        """
        Convert binary representation of nodes to a list of nodes
        """
        node_list = marshal.loads(base64.b64decode(data))
        nodes = []
        for i in range(0, len(node_list), 2):
            nodes.append(node_list[i])
            nodes.append(node_list[i+1])

        return nodes

    def add_nodes(self, object_id:int, nodes: list[Node], properties: dict):
        """
        Add nodes to the database
        """
        bounds = self.find_bounds(nodes)
        if bounds is None:
            return
        
        nodes = self.dump_nodes(nodes)
        properties = json.dumps(properties)

        self.c.execute('''INSERT INTO main_index (id, minx, maxx, miny, maxy, properties) VALUES (?, ?, ?, ?, ?, ?)''', (object_id, bounds[0], bounds[1], bounds[2], bounds[3], properties))
        self.c.execute('''INSERT INTO nodes (id, list) VALUES (?, ?)''', (object_id, nodes))
        self.conn.commit()

    def way(self, w: Way):
        if w.id % 1000 == 0:
            print(str(w.id) + " " * 10, end='\r')

        self.add_nodes(int(w.id), list(w.nodes), dict(w.tags))

if __name__ == "__main__":
    import sys, os

    if len(sys.argv) < 2:
        print("Usage: python3 build_database.py <location.osm.pbf>")
        print("You can download the pbf file from https://download.geofabrik.de/")
        exit(1)

    SRC = sys.argv[1]

    if not os.path.exists(SRC):
        print(f"File {SRC} does not exist!")
        exit(1)

    handler = Handler()
    print("Please wait while the database is built (map.db)")
    print("For large files (~1GB) you may need to wait several hours...")
    print("The final map.db file will be ~3x the size of the pbf file")
    handler.apply_file(SRC, locations=True)
    print("\nFinished!")
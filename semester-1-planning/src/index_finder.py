import carla
import numpy as np

client = carla.Client("localhost", 2000)
client.set_timeout(10.0)
world = client.get_world()

# Get all spawn points
spawn_points = world.get_map().get_spawn_points()

spectator = world.get_spectator()
loc = spectator.get_transform().location
print(loc.x, loc.y, loc.z)

# Location you want
x, y, z = loc.x, loc.y, loc.z

# Compute nearest K spawn points
def nearest_k(spawn_points, x, y, k=5):
    pts = np.array([[sp.location.x, sp.location.y] for sp in spawn_points])
    q = np.array([x, y])
    dists = np.linalg.norm(pts - q, axis=1)
    idxs = np.argsort(dists)[:k]
    return [(int(i), float(dists[i]), spawn_points[i]) for i in idxs]

# Run the search
hits = nearest_k(spawn_points, x, y, k=5)

# Print and visualize
for i, dist, sp in hits:
    print(f"Index {i}: dist={dist:.2f}, loc=({sp.location.x:.2f}, {sp.location.y:.2f}, {sp.location.z:.2f}), yaw={sp.rotation.yaw:.2f}")
    world.debug.draw_string(sp.location, f"{i}", life_time=30.0, color=carla.Color(0, 255, 0))

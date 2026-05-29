# Shared CARLA simulation helpers.


def set_sync(world, enabled=True, dt=0.01):
    s = world.get_settings()
    s.synchronous_mode = enabled
    s.fixed_delta_seconds = dt if enabled else None
    s.substepping = False
    world.apply_settings(s)

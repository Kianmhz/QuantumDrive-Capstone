import json
from pathlib import Path

def save_snapshot(world, ego, ped, cfg, sim_time, path):
    ego_loc = ego.get_location()
    ego_vel = ego.get_velocity()
    ped_loc = ped.get_location()
    ped_vel = ped.get_velocity()

    data = {
        "sim_time": sim_time,
        "cfg": {
            "dt": cfg.dt,
            "horizon_s": cfg.horizon_s,
            "v_ref": cfg.v_ref,
            "d_safe": cfg.d_safe,
        },
        "ego": {
            "loc": [ego_loc.x, ego_loc.y, ego_loc.z],
            "vel": [ego_vel.x, ego_vel.y, ego_vel.z],
            "half_width": 1.0,
        },
        "ped": {
            "loc": [ped_loc.x, ped_loc.y, ped_loc.z],
            "vel": [ped_vel.x, ped_vel.y, ped_vel.z],
        },
    }

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

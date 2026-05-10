import time, math, carla
import json
from pathlib import Path

# ------- Parameters -------
TOWN = "Town04"
EGO_SPEED_MS = 18.0
NPC_SPEED_MS = 24.0
CUTIN_DELAY_S = 2.0
SIM_DT = 0.01
RUNTIME_S = 20.0
REACTION_TIME_S = 0.15
# ---------------------------


def set_sync(world, enabled=True, dt=SIM_DT):
    s = world.get_settings()
    s.synchronous_mode = enabled
    s.fixed_delta_seconds = dt if enabled else None
    s.substepping = False
    world.apply_settings(s)


def fwd(rot):
    yaw = math.radians(rot.yaw)
    return carla.Vector3D(math.cos(yaw), math.sin(yaw), 0)


def right(rot):
    yaw = math.radians(rot.yaw + 90)
    return carla.Vector3D(math.cos(yaw), math.sin(yaw), 0)


def choose_highway_spawn(world):
    spawns = world.get_map().get_spawn_points()
    if len(spawns) > 128:
        return spawns[128]
    else:
        for sp in spawns:
            if abs(sp.location.y) < 5 and sp.location.x > 50:
                return sp
        return spawns[0]


def follow_spectator(world, target, dist=18, height=6):
    spec = world.get_spectator()
    tf = target.get_transform()
    fv = fwd(tf.rotation)
    loc = tf.location - fv * dist
    loc.z += height
    spec.set_transform(carla.Transform(loc, tf.rotation))


def get_distance_between(vehicle1, vehicle2):
    loc1, loc2 = vehicle1.get_location(), vehicle2.get_location()
    return math.sqrt((loc1.x - loc2.x) ** 2 + (loc1.y - loc2.y) ** 2)


def get_relative_position(ego, npc):
    ego_loc, npc_loc = ego.get_location(), npc.get_location()
    ego_tf = ego.get_transform()
    diff = carla.Vector3D(npc_loc.x - ego_loc.x, npc_loc.y - ego_loc.y, 0)
    fv, rv = fwd(ego_tf.rotation), right(ego_tf.rotation)
    return diff.x * fv.x + diff.y * fv.y, diff.x * rv.x + diff.y * rv.y


def classical_decision(ego, npc, distance, longitudinal, lateral, ego_speed, npc_speed):
    CRITICAL_DISTANCE = 12.0
    WARNING_DISTANCE = 20.0
    EMERGENCY_DISTANCE = 5.0  # New threshold for emergency turns
    relative_speed = ego_speed - npc_speed
    ttc = (
        distance / relative_speed
        if relative_speed > 0 and distance > 0
        else float("inf")
    )

    # Determine if NPC is cutting in - Added distance constraint
    is_cutting_in = (
        0.3 < lateral < 3.5 and -5 < longitudinal < 30 and distance < WARNING_DISTANCE
    )
    is_in_lane = (
        abs(lateral) < 1.8 and -3 < longitudinal < 30 and distance < WARNING_DISTANCE
    )
    is_ahead_close = (
        longitudinal > 0
        and longitudinal < 15
        and abs(lateral) < 2.0
        and distance < WARNING_DISTANCE
    )

    # Enhanced decision logic with emergency turns
    if is_in_lane and longitudinal > 0 and distance < CRITICAL_DISTANCE:
        return "hard_brake", "HARD BRAKE - Vehicle in lane!"
    elif is_cutting_in and longitudinal > 0 and distance < WARNING_DISTANCE:
        if ttc < 2.0:  # Reduced from 4.0 to 2.0 for more aggressive reaction
            return "hard_brake", "HARD BRAKE - Cut-in!"
        else:
            return "gentle_brake", "GENTLE BRAKE - Cut-in"
    elif is_ahead_close:
        return "gentle_brake", "GENTLE BRAKE - Vehicle ahead"
    elif is_cutting_in:
        return "gentle_brake", "CAUTION - Merging"
    else:
        return "keep", "KEEP - Safe"


def ego_speed_control(ego, current_speed, target_speed):
    err = target_speed - current_speed
    Kp = 0.12
    throttle = max(0.0, min(0.7, Kp * err))
    brake = 0.0
    if current_speed > target_speed + 0.6:
        # Reduced brake coefficient from 0.06 to 0.03 to prevent sudden stops
        brake = min(0.7, 0.03 * (current_speed - target_speed))
        throttle = 0.0
    ego.apply_control(carla.VehicleControl(throttle=throttle, brake=brake, steer=0.0))


def ego_evasion_control(ego, action, current_speed):
    """Apply evasion control based on action"""
    if action == "hard_turn_left":
        # Hard turn left with reduced speed
        ego.apply_control(
            carla.VehicleControl(
                throttle=0.4,  # Reduce speed during turn
                brake=0.0,
                steer=-0.8,  # Max left turn
            )
        )
    elif action == "hard_turn_right":
        # Hard turn right with reduced speed
        ego.apply_control(
            carla.VehicleControl(
                throttle=0.4,  # Reduce speed during turn
                brake=0.0,
                steer=0.8,  # Max right turn
            )
        )
    elif action == "hard_brake":
        # Hard brake
        ego.apply_control(carla.VehicleControl(throttle=0.0, brake=0.9, steer=0.0))
    elif action == "gentle_brake":
        # Gentle brake
        ego.apply_control(carla.VehicleControl(throttle=0.0, brake=0.45, steer=0.0))
    else:  # "keep"
        # Normal speed control
        ego_speed_control(ego, current_speed, EGO_SPEED_MS)


def save_snapshot(world, ego, npc, sim_time, algorithm_type):
    """Save simulation state for later analysis"""
    snapshot_dir = Path("snapshots")
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    ego_loc = ego.get_location()
    ego_vel = ego.get_velocity()
    npc_loc = npc.get_location()
    npc_vel = npc.get_velocity()

    snapshot = {
        "sim_time": sim_time,
        "ego": {
            "loc": [ego_loc.x, ego_loc.y, ego_loc.z],
            "vel": [ego_vel.x, ego_vel.y, ego_vel.z],
        },
        "npc": {
            "loc": [npc_loc.x, npc_loc.y, npc_loc.z],
            "vel": [npc_vel.x, npc_vel.y, npc_vel.z],
        },
        "meta": {
            "algorithm": algorithm_type,
            "town": TOWN,
        },
    }

    snapshot_path = snapshot_dir / f"cutin_{algorithm_type}_t{sim_time:.2f}.json"
    with open(snapshot_path, "w") as f:
        json.dump(snapshot, f, indent=2)


def main():
    client = carla.Client("localhost", 2000)
    client.set_timeout(10)
    world = client.get_world()

    if world.get_map().name.split("/")[-1] != TOWN:
        world = client.load_world(TOWN)
        time.sleep(0.5)

    bp = world.get_blueprint_library()
    ego_bp = bp.filter("vehicle.tesla.model3")[0]
    npc_bp = bp.filter("vehicle.audi.tt")[0]
    set_sync(world, True)

    actors = []
    decision_made = False

    try:
        ego_spawn = choose_highway_spawn(world)
        ego = world.spawn_actor(ego_bp, ego_spawn)
        actors.append(ego)
        ego.set_autopilot(False)

        fvec, rvec = fwd(ego_spawn.rotation), right(ego_spawn.rotation)

        # Start both cars further back on the highway section
        ego_loc = ego_spawn.location - fvec * 150
        ego_tf = carla.Transform(ego_loc, ego_spawn.rotation)
        ego.set_transform(ego_tf)

        # NPC behind and offset to right lane, further back than before
        npc_loc = ego_loc - fvec * 60 + rvec * 3.6
        npc = world.spawn_actor(npc_bp, carla.Transform(npc_loc, ego_spawn.rotation))
        actors.append(npc)
        npc.set_autopilot(False)

        # Camera
        cam_bp = bp.find("sensor.camera.rgb")
        cam_bp.set_attribute("image_size_x", "640")
        cam_bp.set_attribute("image_size_y", "360")
        cam_bp.set_attribute("fov", "90")
        cam = world.spawn_actor(
            cam_bp, carla.Transform(carla.Location(x=1.5, z=2.2)), attach_to=ego
        )
        actors.append(cam)
        cam.listen(lambda _: None)

        # Behavior tuning
        ticks_total = int(RUNTIME_S / SIM_DT)
        cutin_start_tick = int(CUTIN_DELAY_S / SIM_DT)
        reaction_tick = cutin_start_tick + int(REACTION_TIME_S / SIM_DT)

        LANE_CHANGE_DURATION = int(1.5 / SIM_DT)
        COMPLETION_THRESHOLD = 0.5
        MAX_STEER = 0.5
        Kp, Kd = 0.28, 0.08

        # For print frequency control
        last_print_time = 0
        PRINT_INTERVAL = 1.0  # Print every 1 second

        # For snapshot control
        last_snapshot_time = 0
        SNAPSHOT_INTERVAL = 0.5  # Save snapshot every 0.5 seconds

        print("[Deterministic] HARD early cut-in in front of ego")
        npc_state, lane_change_active = "waiting", False
        lane_change_start_tick, error_prev, steer_prev = None, 0.0, 0.0
        stabilize_start_tick = None
        fine_tune_start_tick = None
        final_stabilize_start_tick = None

        # Damped oscillation parameters
        oscillation_amplitude = 0.0
        oscillation_phase = 0.0
        last_lateral = 0.0

        for tick in range(ticks_total):
            world.tick()
            follow_spectator(world, ego)

            v_ego, v_npc = ego.get_velocity(), npc.get_velocity()
            ego_speed = math.hypot(v_ego.x, v_ego.y)
            npc_speed = math.hypot(v_npc.x, v_npc.y)
            distance = get_distance_between(ego, npc)
            longitudinal, lateral = get_relative_position(ego, npc)

            # --- DEBUG PRINT EVERY SECOND ---
            sim_time = tick * SIM_DT
            if sim_time - last_print_time >= PRINT_INTERVAL:
                print(
                    f"[t={sim_time:05.2f}s] Distance={distance:06.2f}m | EgoSpeed={ego_speed:05.2f}m/s | NPCSpeed={npc_speed:05.2f}m/s"
                )
                last_print_time = sim_time

            # --- SAVE SNAPSHOT ---
            if sim_time - last_snapshot_time >= SNAPSHOT_INTERVAL:
                save_snapshot(world, ego, npc, sim_time, "classical")
                last_snapshot_time = sim_time

            # --- NPC Logic ---
            if tick < cutin_start_tick:
                npc.apply_control(carla.VehicleControl(throttle=0.35))
                npc_state = "waiting"

            elif not lane_change_active and npc_state not in (
                "completed",
                "stabilizing",
                "fine_tuning",
                "final_stabilizing",
            ):
                npc.apply_control(
                    carla.VehicleControl(
                        throttle=0.9 if npc_speed < NPC_SPEED_MS else 0.4
                    )
                )
                npc_state = "approaching"
                # Trigger cut-in closer to ego (reduced from -2.0 to -1.0)
                if longitudinal > -1.0 and lateral > 2.0:
                    lane_change_active = True
                    lane_change_start_tick = tick
                    print(f"\n[✓] HARD CUT-IN TRIGGERED @ {tick * SIM_DT:.2f}s")

            elif (
                lane_change_active
                and (tick - lane_change_start_tick) <= LANE_CHANGE_DURATION
            ):
                progress = (tick - lane_change_start_tick) / float(LANE_CHANGE_DURATION)
                p = progress * progress * (3 - 2 * progress)
                desired_lateral = 3.6 * (1.0 - p)
                error = lateral - desired_lateral
                d_error = (error - error_prev) / SIM_DT
                error_prev = error
                steer = -(Kp * error + Kd * d_error)
                steer = max(-MAX_STEER, min(MAX_STEER, 0.6 * steer_prev + 0.4 * steer))
                steer_prev = steer
                npc.apply_control(carla.VehicleControl(throttle=0.55, steer=steer))
                if abs(lateral) < COMPLETION_THRESHOLD:
                    lane_change_active = False
                    npc_state = "stabilizing"
                    stabilize_start_tick = tick
                    # Initialize damped oscillation parameters
                    oscillation_amplitude = abs(lateral)
                    oscillation_phase = 0.0
                    last_lateral = lateral
                    print(
                        f"[✓] Lane merge done @ {tick * SIM_DT:.2f}s — stabilizing..."
                    )

            elif npc_state == "stabilizing":
                stabilization_duration = int(1.0 / SIM_DT)
                elapsed = tick - stabilize_start_tick

                if elapsed < stabilization_duration:
                    # Stage 1: Damped oscillation for quick correction
                    error = lateral
                    lateral_velocity = (lateral - last_lateral) / SIM_DT
                    last_lateral = lateral

                    # Calculate damping factor (higher for faster damping)
                    damping_factor = 0.7 + 0.2 * (elapsed / stabilization_duration)

                    # Calculate oscillation frequency (decreases over time)
                    frequency = (
                        2.5 * math.pi * (1.0 - 0.5 * (elapsed / stabilization_duration))
                    )

                    # Update oscillation phase
                    oscillation_phase += frequency * SIM_DT

                    # Calculate damped oscillation component
                    oscillation_component = (
                        oscillation_amplitude
                        * math.exp(-damping_factor * elapsed)
                        * math.sin(oscillation_phase)
                    )

                    # Calculate PD control component with higher gains
                    Kp = 0.35
                    Kd = 0.18
                    pd_component = Kp * error + Kd * lateral_velocity

                    # Combine components
                    steer = -(pd_component + 0.3 * oscillation_component)

                    # Allow larger steering angles for quick correction
                    steer = max(-0.35, min(0.35, steer))

                    # Apply control with reduced speed (1-2 m/s faster than ego)
                    target_speed = ego_speed + 1.5
                    throttle = 0.3 if npc_speed < target_speed else 0.2
                    npc.apply_control(
                        carla.VehicleControl(throttle=throttle, steer=steer)
                    )
                else:
                    npc_state = "fine_tuning"
                    fine_tune_start_tick = tick
                    # Reset oscillation parameters for fine-tuning
                    oscillation_amplitude = abs(lateral)
                    oscillation_phase = 0.0
                    print(
                        f"[✓] Quick stabilization done @ {tick * SIM_DT:.2f}s — fine tuning..."
                    )

            elif npc_state == "fine_tuning":
                fine_tune_duration = int(1.0 / SIM_DT)
                elapsed = tick - fine_tune_start_tick

                if elapsed < fine_tune_duration:
                    # Stage 2: Damped oscillation with different parameters for fine-tuning
                    error = lateral
                    lateral_velocity = (lateral - last_lateral) / SIM_DT
                    last_lateral = lateral

                    # Calculate damping factor (higher for faster damping)
                    damping_factor = 0.8 + 0.15 * (elapsed / fine_tune_duration)

                    # Calculate oscillation frequency (lower for fine-tuning)
                    frequency = (
                        1.2 * math.pi * (1.0 - 0.3 * (elapsed / fine_tune_duration))
                    )

                    # Update oscillation phase
                    oscillation_phase += frequency * SIM_DT

                    # Calculate damped oscillation component
                    oscillation_component = (
                        oscillation_amplitude
                        * math.exp(-damping_factor * elapsed)
                        * math.sin(oscillation_phase)
                    )

                    # Calculate PD control component with slightly higher gains
                    Kp = 0.18
                    Kd = 0.1
                    pd_component = Kp * error + Kd * lateral_velocity

                    # Combine components with less oscillation influence
                    steer = -(pd_component + 0.15 * oscillation_component)

                    # Limit to smaller steering angles for fine-tuning
                    steer = max(-0.18, min(0.18, steer))

                    # Apply control with reduced speed (1-2 m/s faster than ego)
                    target_speed = ego_speed + 1.5
                    throttle = 0.3 if npc_speed < target_speed else 0.2
                    npc.apply_control(
                        carla.VehicleControl(throttle=throttle, steer=steer)
                    )
                else:
                    npc_state = "final_stabilizing"
                    final_stabilize_start_tick = tick
                    print(
                        f"[✓] Fine-tuning done @ {tick * SIM_DT:.2f}s — final stabilizing..."
                    )

            elif npc_state == "final_stabilizing":
                final_stabilize_duration = int(0.5 / SIM_DT)
                elapsed = tick - final_stabilize_start_tick

                if elapsed < final_stabilize_duration:
                    # Stage 3: Final stabilization with very gentle control
                    error = lateral
                    d_error = (error - error_prev) / SIM_DT
                    error_prev = error

                    # Very low gains for final stabilization
                    Kp = 0.08
                    Kd = 0.04

                    # Calculate steering with PD controller
                    steer = -(Kp * error + Kd * d_error)

                    # Very limited steering for final stabilization
                    steer = max(-0.08, min(0.08, steer))

                    # Apply control with reduced speed (1-2 m/s faster than ego)
                    target_speed = ego_speed + 1.5
                    throttle = 0.3 if npc_speed < target_speed else 0.2
                    npc.apply_control(
                        carla.VehicleControl(throttle=throttle, steer=steer)
                    )
                else:
                    npc_state = "completed"
                    # Maintain reduced speed
                    target_speed = ego_speed + 1.5
                    throttle = 0.3 if npc_speed < target_speed else 0.2
                    npc.apply_control(
                        carla.VehicleControl(throttle=throttle, steer=0.0)
                    )
                    print(f"[✓] Final stabilization done @ {tick * SIM_DT:.2f}s")

            else:
                # Maintain reduced speed
                target_speed = ego_speed + 1.5
                throttle = 0.3 if npc_speed < target_speed else 0.2
                npc.apply_control(carla.VehicleControl(throttle=throttle))

            # === Ego control ===
            if tick >= reaction_tick:
                action, _ = classical_decision(
                    ego, npc, distance, longitudinal, lateral, ego_speed, npc_speed
                )

                # Debug output to see what decision is being made
                if action != "keep":
                    print(
                        f"[Decision] {action} - Distance: {distance:.2f}m, Longitudinal: {longitudinal:.2f}m, Lateral: {lateral:.2f}m"
                    )

                # Apply the action using the new evasion control function
                ego_evasion_control(ego, action, ego_speed)
            else:
                ego_speed_control(ego, ego_speed, EGO_SPEED_MS)

        print("\n[Scenario Done] Hard early cut-in complete!")

    finally:
        for a in actors[::-1]:
            try:
                a.destroy()
            except:
                pass
        set_sync(world, False)
        print("[Cleaned up]")


if __name__ == "__main__":
    main()

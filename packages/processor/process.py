import sys
import json
import cv2
import numpy as np


# -----------------------------
# Helpers
# -----------------------------

def map_events_to_frames(events, fps):
    for e in events:
        e['frame'] = (e.get('t', 0) / 1000.0) * fps
    return events


def get_latest_event(events, frame_idx):
    valid = [e for e in events if e['frame'] <= frame_idx]
    return valid[-1] if valid else None


def get_interp_pos(events, f_idx, fps):
    if not events:
        return None, None

    if f_idx <= events[0]['frame']:
        return events[0]['x'], events[0]['y']

    for i in range(len(events) - 1):
        e1, e2 = events[i], events[i + 1]
        if e1['frame'] <= f_idx <= e2['frame']:
            gap = e2['frame'] - e1['frame']
            if gap == 0 or gap > 0.1 * fps:
                return e1['x'], e1['y']

            t = (f_idx - e1['frame']) / gap
            x = e1['x'] + (e2['x'] - e1['x']) * t
            y = e1['y'] + (e2['y'] - e1['y']) * t
            return x, y

    return events[-1]['x'], events[-1]['y']


def ease_in_out(t):
    return t * t * (3 - 2 * t)


# -----------------------------
# Intent Logic (SIMPLIFIED 🔥)
# -----------------------------

def get_zoom_target(frame_idx, clicks, fps, idle_frames):
    latest_click = get_latest_event(clicks, frame_idx)
    last_click_f = latest_click['frame'] if latest_click else -9999

    if frame_idx - last_click_f <= idle_frames:
        return 1.8  # strong click zoom

    return 1.0


# -----------------------------
# Main
# -----------------------------

def process_video(video_in, json_in, video_out):

    with open(json_in) as f:
        events = json.load(f)

    cap = cv2.VideoCapture(video_in)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    width = int(cap.get(3))
    height = int(cap.get(4))

    events = map_events_to_frames(events, fps)

    clicks = [e for e in events if e["type"] == "click"]
    moves = [e for e in events if e["type"] == "move"]

    out = cv2.VideoWriter(
        video_out,
        cv2.VideoWriter_fourcc(*'mp4v'),
        fps,
        (width, height)
    )

    # State
    state = {
        "current_target": 1.0,
        "current_scale": 1.0,
        "zoom_start": 1.0,
        "zoom_frame": 0,
        "locked_cx": None,
        "locked_cy": None
    }

    zoom_duration = int(0.25 * fps)

    idle_frames = int(0.3 * fps) + zoom_duration

    # Cursor smoothing state
    smooth_cx = width // 2
    smooth_cy = height // 2

    deadzone = 10  # px
    lerp_factor = 0.15

    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # -----------------------------
        # 1. Intent (CLICK ONLY)
        # -----------------------------
        latest_click = get_latest_event(clicks, frame_idx)
        target = get_zoom_target(frame_idx, clicks, fps, idle_frames)

        # -----------------------------
        # 2. Animate zoom
        # -----------------------------
        if target != state["current_target"]:
            state["zoom_start"] = state["current_scale"]
            state["zoom_frame"] = frame_idx
            state["current_target"] = target
            if target == 1.8:
                state["locked_cx"] = latest_click['x']
                state["locked_cy"] = latest_click['y']

        if frame_idx < state["zoom_frame"] + zoom_duration:
            t = (frame_idx - state["zoom_frame"]) / zoom_duration
            t = ease_in_out(t)
            scale = state["zoom_start"] + \
                (target - state["zoom_start"]) * t
        else:
            scale = target

        state["current_scale"] = scale

        # -----------------------------
        # 3. Cursor Position (SMOOTH 🔥)
        # -----------------------------
        if state["current_scale"] > 1.0:
            # Don't update smooth during zoom
            pass
        else:
            cx, cy = get_interp_pos(moves, frame_idx, fps)

            if cx is None:
                cx, cy = width // 2, height // 2

            # Deadzone (ignore small jitter)
            if abs(cx - smooth_cx) < deadzone and abs(cy - smooth_cy) < deadzone:
                cx, cy = smooth_cx, smooth_cy

            # LERP smoothing
            smooth_cx += (cx - smooth_cx) * lerp_factor
            smooth_cy += (cy - smooth_cy) * lerp_factor

        # -----------------------------
        # 4. Crop
        # -----------------------------
        crop_w = int(width / scale)
        crop_h = int(height / scale)

        if state["current_scale"] > 1.0 and state["locked_cx"] is not None:
            cx = int(np.clip(state["locked_cx"], crop_w // 2, width - crop_w // 2))
            cy = int(np.clip(state["locked_cy"], crop_h // 2, height - crop_h // 2))
        else:
            cx = int(np.clip(smooth_cx, crop_w // 2, width - crop_w // 2))
            cy = int(np.clip(smooth_cy, crop_h // 2, height - crop_h // 2))

        x1 = cx - crop_w // 2
        y1 = cy - crop_h // 2

        cropped = frame[y1:y1 + crop_h, x1:x1 + crop_w]

        if cropped.size == 0:
            out.write(frame)
        else:
            resized = cv2.resize(cropped, (width, height))
            out.write(resized)

        frame_idx += 1

    cap.release()
    out.release()


if __name__ == "__main__":
    process_video(sys.argv[1], sys.argv[2], sys.argv[3])
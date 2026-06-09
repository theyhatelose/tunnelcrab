from PIL import Image, ImageDraw


def render_crab_image(state="idle", frame=0, canvas_size=120):
    img = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
    drawer = ImageDraw.Draw(img)
    origin_x, origin_y = 60, 60

    walking = state in {"connecting", "easter"}
    happy = state == "connected"
    error = state == "error"

    if error:
        leg_colors = ["#ff7a7a", "#c7465c"]
    elif happy:
        leg_colors = ["#4ecca3", "#35b48b"] if frame % 2 == 0 else ["#35b48b", "#4ecca3"]
    elif walking:
        leg_colors = ["#e94560", "#ff6b8a"] if frame % 2 == 0 else ["#ff6b8a", "#e94560"]
    else:
        leg_colors = ["#e94560", "#c73652"]

    body_color = "#ff8b8b" if error else "#4ecca3" if happy else "#e94560"
    claw_color = "#d95c6e" if error else "#35b48b" if happy else "#c73652"
    body_y_shift = -2 if happy and frame % 2 == 0 else 2 if happy else 0
    tilt = 3 if error and frame % 2 == 0 else -3 if error else 0

    for index, (dx, dy) in enumerate([(-35, -10), (-40, 0), (-35, 10)]):
        drawer.line(
            [
                (origin_x - 18, origin_y + index * 8 - 8 + body_y_shift),
                (origin_x + dx, origin_y + dy + index * 8 - 8 + body_y_shift),
            ],
            fill=leg_colors[index % 2],
            width=3,
        )

    for index, (dx, dy) in enumerate([(35, -10), (40, 0), (35, 10)]):
        drawer.line(
            [
                (origin_x + 18, origin_y + index * 8 - 8 + body_y_shift),
                (origin_x + dx, origin_y + dy + index * 8 - 8 + body_y_shift),
            ],
            fill=leg_colors[index % 2],
            width=3,
        )

    drawer.ellipse(
        [origin_x - 22, origin_y - 15 + body_y_shift, origin_x + 22, origin_y + 15 + body_y_shift],
        fill=body_color,
    )

    claw_offset = 5 if walking and frame % 2 == 0 else -2 if happy else 0
    drawer.ellipse(
        [
            origin_x - 48,
            origin_y - 25 + claw_offset + body_y_shift + tilt,
            origin_x - 28,
            origin_y - 5 + claw_offset + body_y_shift,
        ],
        fill=claw_color,
    )
    drawer.ellipse(
        [
            origin_x + 28,
            origin_y - 25 + claw_offset + body_y_shift,
            origin_x + 48,
            origin_y - 5 + claw_offset + body_y_shift + tilt,
        ],
        fill=claw_color,
    )

    eye_y = origin_y - 10 + body_y_shift
    if walking:
        eye_y += 1 if frame % 2 == 0 else -1
    if error:
        eye_y += 2
    drawer.ellipse([origin_x - 10, eye_y - 6, origin_x - 2, eye_y + 2], fill="white")
    drawer.ellipse([origin_x + 2, eye_y - 6, origin_x + 10, eye_y + 2], fill="white")
    if error:
        drawer.line([(origin_x - 8, eye_y - 5), (origin_x - 4, eye_y + 1)], fill="#1a1a2e", width=2)
        drawer.line([(origin_x - 8, eye_y + 1), (origin_x - 4, eye_y - 5)], fill="#1a1a2e", width=2)
        drawer.line([(origin_x + 4, eye_y - 5), (origin_x + 8, eye_y + 1)], fill="#1a1a2e", width=2)
        drawer.line([(origin_x + 4, eye_y + 1), (origin_x + 8, eye_y - 5)], fill="#1a1a2e", width=2)
    else:
        drawer.ellipse([origin_x - 8, eye_y - 5, origin_x - 4, eye_y + 1], fill="#1a1a2e")
        drawer.ellipse([origin_x + 4, eye_y - 5, origin_x + 8, eye_y + 1], fill="#1a1a2e")

    if happy:
        drawer.arc(
            [origin_x - 10, origin_y - 2 + body_y_shift, origin_x + 10, origin_y + 10 + body_y_shift],
            start=20,
            end=160,
            fill="#102020",
            width=2,
        )
    elif error:
        drawer.arc(
            [origin_x - 10, origin_y + 2 + body_y_shift, origin_x + 10, origin_y + 12 + body_y_shift],
            start=200,
            end=340,
            fill="#3a1820",
            width=2,
        )

    if canvas_size != 120:
        img = img.resize((canvas_size, canvas_size), Image.Resampling.LANCZOS)

    return img

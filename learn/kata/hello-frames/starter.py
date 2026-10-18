frames = "\n".join(
    [
        ";;; ── frames ──",
        "1 | 1 2 3 +\t; 2 3 4",
        "1 2 3 +\t; [1‿2‿3 +]",
        "2 | 3 +\t; 5",
        "1 | 1 2 3 [-] swap-args\t; 1 2 3 - 1",
    ]
)
print(fpl.run.default.src(frames), end="")

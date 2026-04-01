import subprocess
import os


def stitchVideo(topics, source_path, output_path):
    kept_segments = []

    # Step 1 — collect all kept segments with their timestamps
    for topic in topics:
        for seg in topic:
            if seg.keep:
                kept_segments.append(seg)

    # Sort by start time just in case they're out of order
    kept_segments.sort(key=lambda s: s.start)

    if not kept_segments:
        print("No segments were kept. Nothing to stitch.")
        return

    os.makedirs("temp_clips", exist_ok=True)

    # Step 2 — cut each kept segment into a temp clip
    clip_paths = []
    for i, seg in enumerate(kept_segments):
        clip_path = os.path.abspath(f"temp_clips/temp_clip_{i}.mp4")

        subprocess.run([
            "ffmpeg", "-y",
            "-ss", str(seg.start),
            "-to", str(seg.end),
            "-i", source_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            clip_path
        ], check=True)

        clip_paths.append(clip_path)

    # Step 3 — write a concat list file for FFmpeg
    concat_file = os.path.abspath("temp_clips/concat_list.txt")
    with open(concat_file, "w") as f:
        for path in clip_paths:
            f.write(f"file '{path}'\n")

    # Step 4 — concatenate all clips into final output
    output_path = os.path.abspath(output_path)

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        output_path
    ], check=True)

    print(f"Final stitched video saved to: {output_path}")

    # Step 5 — cleanup temp files
    for path in clip_paths:
        if os.path.exists(path):
            os.remove(path)

    if os.path.exists(concat_file):
        os.remove(concat_file)

    if os.path.exists("temp_clips") and not os.listdir("temp_clips"):
        os.rmdir("temp_clips")
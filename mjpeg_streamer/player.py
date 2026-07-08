from aiohttp import web


class PlayerHandler:
    def __init__(self, server) -> None:
        self._server = server

    async def __call__(self, request: web.Request) -> web.Response:
        video_streams = self._server._cap_routes
        audio_streams = self._server._audio_routes
        host = self._server._host[0]
        port = self._server._port
        has_video = len(video_streams) > 0
        has_audio = len(audio_streams) > 0

        video_options = "\n".join(
            f'<option value="http://{host}:{port}{r}">{r.lstrip("/")}</option>'
            for r in video_streams
        )
        audio_options = "\n".join(
            f'<option value="http://{host}:{port}{r}">{r.lstrip("/")}</option>'
            for r in audio_streams
        )

        video_section = ""
        video_js = ""
        if has_video:
            video_section = """
  <div class="player" id="videoPlayer">
    <img id="video" alt="video stream">
    <div class="status" id="status">Stopped</div>
  </div>"""
            video_js = """
  const videoImg = document.getElementById('video');
  const statusEl = document.getElementById('status');
  const videoSelect = document.getElementById('videoSelect');"""

        controls_html = ""
        if has_video:
            controls_html += '  <select id="videoSelect">{video_options}</select>\n'
        if has_audio:
            controls_html += '  <select id="audioSelect"><option value="">No audio</option>{audio_options}</select>\n'
        controls_html += '  <button id="playBtn">Play</button>'

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stream Player</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #1a1a2e; color: #eee; font-family: system-ui, sans-serif; display: flex; flex-direction: column; align-items: center; min-height: 100vh; padding: 20px; }}
  h1 {{ margin-bottom: 16px; font-size: 1.4rem; color: #e94560; }}
  .controls {{ display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; justify-content: center; }}
  select, button {{ padding: 8px 14px; border: 1px solid #333; border-radius: 6px; background: #16213e; color: #eee; font-size: 0.9rem; cursor: pointer; }}
  select:hover, button:hover {{ border-color: #e94560; }}
  button.active {{ background: #e94560; border-color: #e94560; }}
  .player {{ position: relative; background: #000; border-radius: 8px; overflow: hidden; max-width: 90vw; }}
  #video {{ display: block; max-width: 90vw; max-height: 80vh; object-fit: contain; }}
  .status {{ position: absolute; top: 8px; left: 8px; background: rgba(0,0,0,0.7); padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; color: #0f0; }}
  .status.error {{ color: #f44; }}
  .volume {{ display: flex; align-items: center; gap: 6px; margin-top: 10px; }}
  .volume input[type=range] {{ width: 120px; accent-color: #e94560; }}
  .audio-only {{ background: #16213e; border-radius: 8px; padding: 30px 40px; text-align: center; margin: 10px 0; }}
  .audio-only .icon {{ font-size: 3rem; margin-bottom: 10px; }}
  .audio-only .label {{ color: #aaa; font-size: 0.9rem; }}
</style>
</head>
<body>
<h1>Stream Player</h1>
<div class="controls">
{controls_html.format(video_options=video_options, audio_options=audio_options)}
</div>
{video_section}
{"<div class='audio-only' id='audioPlayer'><div class='icon'>&#9835;</div><div class='label'>Audio stream</div></div>" if not has_video else ""}
<div class="volume">
  <label for="volumeSlider">Vol:</label>
  <input type="range" id="volumeSlider" min="0" max="1" step="0.05" value="1">
  <span id="volumeVal">100%</span>
</div>
<audio id="audio" autoplay></audio>
<script>
  {video_js}
  const audioEl = document.getElementById('audio');
  const playBtn = document.getElementById('playBtn');
  const volumeSlider = document.getElementById('volumeSlider');
  const volumeVal = document.getElementById('volumeVal');
  let playing = false;
  {'const audioSelect = document.getElementById("audioSelect");' if has_audio else ''}

  function startStreams() {{
    {'const vUrl = videoSelect.value;' if has_video else ''}
    {'if (!vUrl) return;' if has_video else ''}
    {f'videoImg.src = vUrl;' if has_video else ''}
    {'const aUrl = audioSelect.value;' if has_audio else ''}
    {f'''if (aUrl) {{
      audioEl.src = aUrl;
      audioEl.play().catch(() => {{}});
    }} else {{
      audioEl.src = '';
    }}''' if has_audio else ''}
    {f"statusEl.textContent = 'Playing'; statusEl.className = 'status';" if has_video else ''}
    playing = true;
    playBtn.textContent = 'Stop';
    playBtn.classList.add('active');
  }}

  function stopStreams() {{
    {f"videoImg.src = '';" if has_video else ''}
    audioEl.pause();
    audioEl.src = '';
    {f"statusEl.textContent = 'Stopped'; statusEl.className = 'status error';" if has_video else ''}
    playing = false;
    playBtn.textContent = 'Play';
    playBtn.classList.remove('active');
  }}

  playBtn.addEventListener('click', () => {{
    playing ? stopStreams() : startStreams();
  }});

  {'videoSelect.addEventListener("change", () => {{ if (playing) {{ videoImg.src = videoSelect.value; }} }});' if has_video else ''}

  {'audioSelect.addEventListener("change", () => {{ if (playing) {{ const aUrl = audioSelect.value; if (aUrl) {{ audioEl.src = aUrl; audioEl.play().catch(() => {{}}); }} else {{ audioEl.pause(); audioEl.src = ""; }} }} }});' if has_audio else ''}

  volumeSlider.addEventListener('input', () => {{
    const v = parseFloat(volumeSlider.value);
    audioEl.volume = v;
    volumeVal.textContent = Math.round(v * 100) + '%';
  }});

  audioEl.addEventListener('playing', () => {{
    {f"statusEl.textContent = 'Playing (audio synced)';" if has_video else ''}
  }});

  audioEl.addEventListener('error', () => {{
    {f"if (playing) statusEl.textContent = 'Playing (video only)';" if has_video else ''}
  }});

  {'videoImg.addEventListener("error", () => {{ if (playing) {{ statusEl.textContent = "Connection lost"; statusEl.className = "status error"; }} }});' if has_video else ''}
</script>
</body>
</html>"""
        return web.Response(text=html, content_type="text/html")

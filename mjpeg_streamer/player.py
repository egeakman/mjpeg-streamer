from aiohttp import web


class PlayerHandler:
    def __init__(self, server) -> None:
        self._server = server

    async def __call__(self, request: web.Request) -> web.Response:
        video_streams = self._server._cap_routes
        audio_streams = self._server._audio_routes
        host = self._server._host[0]
        port = self._server._port

        video_options = "\n".join(
            f'<option value="http://{host}:{port}{r}">{r.lstrip("/")}</option>'
            for r in video_streams
        )
        audio_options = "\n".join(
            f'<option value="http://{host}:{port}{r}">{r.lstrip("/")}</option>'
            for r in audio_streams
        )

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
</style>
</head>
<body>
<h1>Stream Player</h1>
<div class="controls">
  <select id="videoSelect">{video_options}</select>
  <select id="audioSelect"><option value="">No audio</option>{audio_options}</select>
  <button id="playBtn">Play</button>
</div>
<div class="player">
  <img id="video" alt="video stream">
  <div class="status" id="status">Stopped</div>
</div>
<div class="volume">
  <label for="volumeSlider">Vol:</label>
  <input type="range" id="volumeSlider" min="0" max="1" step="0.05" value="1">
  <span id="volumeVal">100%</span>
</div>
<audio id="audio" autoplay></audio>
<script>
  const videoImg = document.getElementById('video');
  const audioEl = document.getElementById('audio');
  const statusEl = document.getElementById('status');
  const videoSelect = document.getElementById('videoSelect');
  const audioSelect = document.getElementById('audioSelect');
  const playBtn = document.getElementById('playBtn');
  const volumeSlider = document.getElementById('volumeSlider');
  const volumeVal = document.getElementById('volumeVal');
  let playing = false;

  function startStreams() {{
    const vUrl = videoSelect.value;
    if (!vUrl) return;
    videoImg.src = vUrl;
    const aUrl = audioSelect.value;
    if (aUrl) {{
      audioEl.src = aUrl;
      audioEl.play().catch(() => {{}});
    }} else {{
      audioEl.src = '';
    }}
    statusEl.textContent = 'Playing';
    statusEl.className = 'status';
    playing = true;
    playBtn.textContent = 'Stop';
    playBtn.classList.add('active');
  }}

  function stopStreams() {{
    videoImg.src = '';
    audioEl.pause();
    audioEl.src = '';
    statusEl.textContent = 'Stopped';
    statusEl.className = 'status error';
    playing = false;
    playBtn.textContent = 'Play';
    playBtn.classList.remove('active');
  }}

  playBtn.addEventListener('click', () => {{
    playing ? stopStreams() : startStreams();
  }});

  videoSelect.addEventListener('change', () => {{
    if (playing) {{
      videoImg.src = videoSelect.value;
    }}
  }});

  audioSelect.addEventListener('change', () => {{
    if (playing) {{
      const aUrl = audioSelect.value;
      if (aUrl) {{
        audioEl.src = aUrl;
        audioEl.play().catch(() => {{}});
      }} else {{
        audioEl.pause();
        audioEl.src = '';
      }}
    }}
  }});

  volumeSlider.addEventListener('input', () => {{
    const v = parseFloat(volumeSlider.value);
    audioEl.volume = v;
    volumeVal.textContent = Math.round(v * 100) + '%';
  }});

  audioEl.addEventListener('playing', () => {{
    statusEl.textContent = 'Playing (audio synced)';
  }});

  audioEl.addEventListener('error', () => {{
    if (playing) statusEl.textContent = 'Playing (video only)';
  }});

  videoImg.addEventListener('error', () => {{
    if (playing) {{
      statusEl.textContent = 'Connection lost';
      statusEl.className = 'status error';
    }}
  }});
</script>
</body>
</html>"""
        return web.Response(text=html, content_type="text/html")

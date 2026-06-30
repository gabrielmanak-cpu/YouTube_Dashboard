"""
YouTube Channel + Trades Content Scraper
-----------------------------------------
Pulls recent video stats from competitor channels
and searches for top-performing trades content by keyword.

Usage:
    python youtube_scraper.py

Set your API key in the script or as an env variable:
    export YOUTUBE_API_KEY=your_key_here
"""

import os
import csv
import re
import datetime
from googleapiclient.discovery import build

# ----------------------------
# CONFIG — edit these
# ----------------------------

API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

CHANNELS = [
    # Software competitors
    "@Housecallpro",
    "@Jobber",
    "@ServiceTitan",
    "@workiz",
    "@MyQuoteIQ",
]

INSPIRATION_CHANNELS = [
    # High-performing trades creators (feeds Trending Trades tab)
    "@ElectricianU",
    "@OhYouBetcha",
    "@CarlMurawski",
]

TRADES_KEYWORDS = [
    "HVAC tips",
    "plumbing tips",
    "electrician tips",
    "field service business",
    "home service business",
]

VIDEOS_PER_CHANNEL = 20       # recent videos to pull per channel
SEARCH_RESULTS_PER_KEYWORD = 10  # top videos per keyword search
SEARCH_DAYS_BACK = 90         # only return keyword search results from this many days ago
OUTPUT_FILE = "youtube_data.csv"

# ----------------------------
# HELPERS
# ----------------------------

MIN_DURATION_SECONDS = 180  # filter out anything under 3 minutes (shorts)


def parse_duration(iso_duration):
    """Convert ISO 8601 duration (PT4M13S) to total seconds."""
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso_duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def get_youtube_client():
    return build("youtube", "v3", developerKey=API_KEY)


def resolve_channel_id(youtube, handle):
    """Convert a @handle to a channel ID."""
    response = youtube.channels().list(
        part="id,snippet",
        forHandle=handle.lstrip("@")
    ).execute()
    items = response.get("items", [])
    if not items:
        print(f"  Could not find channel: {handle}")
        return None, None
    channel = items[0]
    return channel["id"], channel["snippet"]["title"]


def get_recent_videos(youtube, channel_id, channel_name, max_results=20):
    """Get recent videos from a channel with view/like/comment stats."""
    # Step 1: search for recent videos
    search_response = youtube.search().list(
        part="id,snippet",
        channelId=channel_id,
        order="date",
        type="video",
        maxResults=max_results
    ).execute()

    video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]
    if not video_ids:
        return []

    # Step 2: get stats for those videos
    stats_response = youtube.videos().list(
        part="statistics,contentDetails,snippet",
        id=",".join(video_ids)
    ).execute()

    videos = []
    for item in stats_response.get("items", []):
        duration = item["contentDetails"]["duration"]
        if parse_duration(duration) < MIN_DURATION_SECONDS:
            continue  # skip shorts
        stats = item.get("statistics", {})
        videos.append({
            "source": "channel",
            "channel": channel_name,
            "video_id": item["id"],
            "title": item["snippet"]["title"],
            "published_at": item["snippet"]["publishedAt"][:10],
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "duration": duration,
            "url": f"https://youtube.com/watch?v={item['id']}",
        })
    return videos


def search_trades_content(youtube, keyword, max_results=10):
    """Search for top-performing videos by keyword."""
    published_after = (datetime.datetime.utcnow() - datetime.timedelta(days=SEARCH_DAYS_BACK)).strftime("%Y-%m-%dT%H:%M:%SZ")
    search_response = youtube.search().list(
        part="id,snippet",
        q=keyword,
        order="viewCount",
        type="video",
        videoDuration="medium",  # excludes shorts (< 4 min) at API level
        publishedAfter=published_after,
        maxResults=max_results,
        relevanceLanguage="en",
    ).execute()

    video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]
    if not video_ids:
        return []

    stats_response = youtube.videos().list(
        part="statistics,contentDetails,snippet",
        id=",".join(video_ids)
    ).execute()

    videos = []
    for item in stats_response.get("items", []):
        duration = item["contentDetails"]["duration"]
        if parse_duration(duration) < MIN_DURATION_SECONDS:
            continue  # belt-and-suspenders filter on top of videoDuration param
        stats = item.get("statistics", {})
        videos.append({
            "source": f"search: {keyword}",
            "channel": item["snippet"]["channelTitle"],
            "video_id": item["id"],
            "title": item["snippet"]["title"],
            "published_at": item["snippet"]["publishedAt"][:10],
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "duration": duration,
            "url": f"https://youtube.com/watch?v={item['id']}",
        })
    return videos


def save_to_csv(rows, filename):
    if not rows:
        print("No data to save.")
        return
    fields = ["source", "channel", "title", "views", "likes", "comments",
              "published_at", "duration", "url", "video_id"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} rows to {filename}")


def build_dashboard(rows, filename="dashboard.html"):
    import json
    updated = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p")
    data_json = json.dumps(rows)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>YouTube Brand Intelligence</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0f0f13; color: #e0e0e0; min-height: 100vh; }}
  header {{ background: #1a1a24; border-bottom: 1px solid #2a2a3a; padding: 20px 32px; display: flex; justify-content: space-between; align-items: center; }}
  header h1 {{ font-size: 20px; font-weight: 600; color: #fff; letter-spacing: -0.3px; }}
  header span {{ font-size: 12px; color: #666; }}
  .container {{ max-width: 1300px; margin: 0 auto; padding: 28px 32px; }}
  .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
  .card {{ background: #1a1a24; border: 1px solid #2a2a3a; border-radius: 10px; padding: 20px; }}
  .card .label {{ font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px; }}
  .card .value {{ font-size: 28px; font-weight: 700; color: #fff; }}
  .card .sub {{ font-size: 12px; color: #888; margin-top: 4px; }}
  .tabs {{ display: flex; gap: 4px; margin-bottom: 20px; }}
  .tab {{ padding: 8px 18px; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; border: none; background: transparent; color: #888; transition: all 0.15s; }}
  .tab.active {{ background: #2a2a3a; color: #fff; }}
  .tab:hover:not(.active) {{ color: #ccc; }}
  .panel {{ display: none; }}
  .panel.active {{ display: block; }}
  .toolbar {{ display: flex; gap: 12px; margin-bottom: 16px; align-items: center; flex-wrap: wrap; }}
  .toolbar input {{ background: #1a1a24; border: 1px solid #2a2a3a; border-radius: 6px; padding: 8px 12px; color: #e0e0e0; font-size: 13px; width: 240px; outline: none; }}
  .toolbar input:focus {{ border-color: #4a4a6a; }}
  .toolbar select {{ background: #1a1a24; border: 1px solid #2a2a3a; border-radius: 6px; padding: 8px 12px; color: #e0e0e0; font-size: 13px; outline: none; cursor: pointer; }}
  .count {{ font-size: 12px; color: #666; margin-left: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: #1a1a24; color: #888; font-weight: 500; text-align: left; padding: 10px 12px; border-bottom: 1px solid #2a2a3a; cursor: pointer; white-space: nowrap; user-select: none; }}
  th:hover {{ color: #ccc; }}
  th.sorted-asc::after {{ content: " ↑"; color: #6c8fff; }}
  th.sorted-desc::after {{ content: " ↓"; color: #6c8fff; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #1e1e28; vertical-align: middle; }}
  tr:hover td {{ background: #1e1e2a; }}
  .title-cell {{ max-width: 340px; }}
  .title-cell a {{ color: #8ab4f8; text-decoration: none; font-weight: 500; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.4; }}
  .title-cell a:hover {{ color: #aac8ff; }}
  .channel-badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; white-space: nowrap; }}
  .views {{ font-weight: 600; color: #fff; }}
  .date {{ color: #666; white-space: nowrap; }}
  .chart-wrap {{ background: #1a1a24; border: 1px solid #2a2a3a; border-radius: 10px; padding: 24px; margin-bottom: 24px; }}
  .chart-wrap h3 {{ font-size: 14px; font-weight: 600; color: #ccc; margin-bottom: 20px; }}
  .chart-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px; }}
  .empty {{ text-align: center; padding: 48px; color: #555; font-size: 14px; }}
</style>
</head>
<body>

<header>
  <h1>YouTube Brand Intelligence</h1>
  <span>Last updated: {updated}</span>
</header>

<div class="container">

  <div class="cards" id="summary-cards"></div>

  <div class="tabs">
    <button class="tab active" onclick="switchTab('competitors')">Competitor Channels</button>
    <button class="tab" onclick="switchTab('trends')">Trending Trades</button>
    <button class="tab" onclick="switchTab('charts')">Charts</button>
  </div>

  <!-- Competitors Panel -->
  <div class="panel active" id="panel-competitors">
    <div class="toolbar">
      <input type="text" id="comp-search" placeholder="Search titles..." oninput="renderCompetitors()">
      <select id="comp-channel" onchange="renderCompetitors()"><option value="">All channels</option></select>
      <span class="count" id="comp-count"></span>
    </div>
    <table id="comp-table">
      <thead>
        <tr>
          <th onclick="sortTable('competitors','title')">Title</th>
          <th onclick="sortTable('competitors','channel')">Channel</th>
          <th onclick="sortTable('competitors','views')">Views</th>
          <th onclick="sortTable('competitors','likes')">Likes</th>
          <th onclick="sortTable('competitors','comments')">Comments</th>
          <th onclick="sortTable('competitors','published_at')">Published</th>
        </tr>
      </thead>
      <tbody id="comp-body"></tbody>
    </table>
  </div>

  <!-- Trending Panel -->
  <div class="panel" id="panel-trends">
    <div class="toolbar">
      <input type="text" id="trend-search" placeholder="Search titles..." oninput="renderTrends()">
      <select id="trend-keyword" onchange="renderTrends()"><option value="">All keywords</option></select>
      <span class="count" id="trend-count"></span>
    </div>
    <table id="trend-table">
      <thead>
        <tr>
          <th onclick="sortTable('trends','title')">Title</th>
          <th onclick="sortTable('trends','channel')">Channel</th>
          <th onclick="sortTable('trends','source')">Keyword</th>
          <th onclick="sortTable('trends','views')">Views</th>
          <th onclick="sortTable('trends','likes')">Likes</th>
          <th onclick="sortTable('trends','published_at')">Published</th>
        </tr>
      </thead>
      <tbody id="trend-body"></tbody>
    </table>
  </div>

  <!-- Charts Panel -->
  <div class="panel" id="panel-charts">
    <div class="chart-row">
      <div class="chart-wrap">
        <h3>Avg Views per Video by Channel</h3>
        <canvas id="chart-avg-views" height="220"></canvas>
      </div>
      <div class="chart-wrap">
        <h3>Videos Posted (Last 90 Days) by Channel</h3>
        <canvas id="chart-video-count" height="220"></canvas>
      </div>
    </div>
    <div class="chart-wrap">
      <h3>Top 10 Trending Trades Videos by Views</h3>
      <canvas id="chart-top-trends" height="160"></canvas>
    </div>
  </div>

</div>

<script>
const RAW = {data_json};
const CHANNEL_COLORS = {{}};
const PALETTE = ['#6c8fff','#ff6c8f','#6cffa0','#ffb86c','#c86cff','#6cefff','#ffef6c','#ff8f6c'];
let sortState = {{ competitors: {{ col: 'views', dir: 'desc' }}, trends: {{ col: 'views', dir: 'desc' }} }};

const competitors = RAW.filter(r => r.source === 'channel');
const trends = RAW.filter(r => r.source !== 'channel');

// Assign colors to channels
[...new Set(RAW.map(r => r.channel))].forEach((ch, i) => {{
  CHANNEL_COLORS[ch] = PALETTE[i % PALETTE.length];
}});

function fmtNum(n) {{
  if (n >= 1000000) return (n/1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n/1000).toFixed(1) + 'K';
  return n.toString();
}}

function channelBadge(ch) {{
  const color = CHANNEL_COLORS[ch] || '#888';
  return `<span class="channel-badge" style="background:${{color}}22;color:${{color}}">${{ch}}</span>`;
}}

// Summary cards
function buildCards() {{
  const totalVideos = RAW.length;
  const channels = [...new Set(competitors.map(r => r.channel))];
  const topVideo = [...competitors].sort((a,b) => b.views - a.views)[0];
  const avgViews = competitors.length ? Math.round(competitors.reduce((s,r) => s + r.views, 0) / competitors.length) : 0;

  document.getElementById('summary-cards').innerHTML = `
    <div class="card"><div class="label">Total Videos</div><div class="value">${{totalVideos}}</div><div class="sub">across all sources</div></div>
    <div class="card"><div class="label">Channels Tracked</div><div class="value">${{channels.length}}</div><div class="sub">${{channels.join(', ')}}</div></div>
    <div class="card"><div class="label">Top Video Views</div><div class="value">${{fmtNum(topVideo?.views || 0)}}</div><div class="sub">${{topVideo?.channel || ''}}</div></div>
    <div class="card"><div class="label">Avg Views / Video</div><div class="value">${{fmtNum(avgViews)}}</div><div class="sub">competitor channels</div></div>
  `;
}}

// Populate filter dropdowns
function buildFilters() {{
  const compChannels = [...new Set(competitors.map(r => r.channel))].sort();
  const sel1 = document.getElementById('comp-channel');
  compChannels.forEach(ch => sel1.innerHTML += `<option value="${{ch}}">${{ch}}</option>`);

  const keywords = [...new Set(trends.map(r => r.source))].sort();
  const sel2 = document.getElementById('trend-keyword');
  keywords.forEach(kw => sel2.innerHTML += `<option value="${{kw}}">${{kw.replace('search: ','')}}</option>`);
}}

function sortTable(table, col) {{
  const state = sortState[table];
  state.dir = (state.col === col && state.dir === 'desc') ? 'asc' : 'desc';
  state.col = col;
  table === 'competitors' ? renderCompetitors() : renderTrends();
}}

function applySort(data, col, dir) {{
  return [...data].sort((a, b) => {{
    let av = a[col], bv = b[col];
    if (typeof av === 'string') return dir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
    return dir === 'asc' ? av - bv : bv - av;
  }});
}}

function updateSortHeaders(tableId, col, dir) {{
  document.querySelectorAll(`#${{tableId}} th`).forEach(th => {{
    th.classList.remove('sorted-asc','sorted-desc');
    if (th.textContent.trim().toLowerCase().startsWith(col.toLowerCase())) {{
      th.classList.add(dir === 'asc' ? 'sorted-asc' : 'sorted-desc');
    }}
  }});
}}

function renderCompetitors() {{
  const search = document.getElementById('comp-search').value.toLowerCase();
  const channel = document.getElementById('comp-channel').value;
  const {{ col, dir }} = sortState.competitors;

  let data = competitors.filter(r =>
    (!channel || r.channel === channel) &&
    (!search || r.title.toLowerCase().includes(search))
  );
  data = applySort(data, col, dir);

  document.getElementById('comp-count').textContent = `${{data.length}} videos`;
  updateSortHeaders('comp-table', col, dir);

  document.getElementById('comp-body').innerHTML = data.map(r => `
    <tr>
      <td class="title-cell"><a href="${{r.url}}" target="_blank">${{r.title}}</a></td>
      <td>${{channelBadge(r.channel)}}</td>
      <td class="views">${{fmtNum(r.views)}}</td>
      <td>${{fmtNum(r.likes)}}</td>
      <td>${{fmtNum(r.comments)}}</td>
      <td class="date">${{r.published_at}}</td>
    </tr>
  `).join('') || '<tr><td colspan="6" class="empty">No results</td></tr>';
}}

function renderTrends() {{
  const search = document.getElementById('trend-search').value.toLowerCase();
  const keyword = document.getElementById('trend-keyword').value;
  const {{ col, dir }} = sortState.trends;

  let data = trends.filter(r =>
    (!keyword || r.source === keyword) &&
    (!search || r.title.toLowerCase().includes(search))
  );
  data = applySort(data, col, dir);

  document.getElementById('trend-count').textContent = `${{data.length}} videos`;
  updateSortHeaders('trend-table', col, dir);

  document.getElementById('trend-body').innerHTML = data.map(r => `
    <tr>
      <td class="title-cell"><a href="${{r.url}}" target="_blank">${{r.title}}</a></td>
      <td>${{channelBadge(r.channel)}}</td>
      <td><span style="color:#888;font-size:12px">${{r.source.replace('search: ','')}}</span></td>
      <td class="views">${{fmtNum(r.views)}}</td>
      <td>${{fmtNum(r.likes)}}</td>
      <td class="date">${{r.published_at}}</td>
    </tr>
  `).join('') || '<tr><td colspan="6" class="empty">No results</td></tr>';
}}

function buildCharts() {{
  const channels = [...new Set(competitors.map(r => r.channel))];
  const avgViews = channels.map(ch => {{
    const vids = competitors.filter(r => r.channel === ch);
    return Math.round(vids.reduce((s,r) => s+r.views,0) / vids.length);
  }});
  const videoCounts = channels.map(ch => competitors.filter(r => r.channel === ch).length);
  const colors = channels.map(ch => CHANNEL_COLORS[ch] || '#888');

  new Chart(document.getElementById('chart-avg-views'), {{
    type: 'bar',
    data: {{ labels: channels, datasets: [{{ data: avgViews, backgroundColor: colors, borderRadius: 6 }}] }},
    options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ x: {{ ticks: {{ color: '#888' }}, grid: {{ color: '#1e1e28' }} }}, y: {{ ticks: {{ color: '#888', callback: v => fmtNum(v) }}, grid: {{ color: '#1e1e28' }} }} }} }}
  }});

  new Chart(document.getElementById('chart-video-count'), {{
    type: 'bar',
    data: {{ labels: channels, datasets: [{{ data: videoCounts, backgroundColor: colors, borderRadius: 6 }}] }},
    options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ x: {{ ticks: {{ color: '#888' }}, grid: {{ color: '#1e1e28' }} }}, y: {{ ticks: {{ color: '#888' }}, grid: {{ color: '#1e1e28' }} }} }} }}
  }});

  const top10 = applySort(trends, 'views', 'desc').slice(0, 10);
  new Chart(document.getElementById('chart-top-trends'), {{
    type: 'bar',
    indexAxis: 'y',
    data: {{
      labels: top10.map(r => r.title.length > 50 ? r.title.slice(0,50)+'...' : r.title),
      datasets: [{{ data: top10.map(r => r.views), backgroundColor: '#6c8fff88', borderColor: '#6c8fff', borderWidth: 1, borderRadius: 4 }}]
    }},
    options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ x: {{ ticks: {{ color: '#888', callback: v => fmtNum(v) }}, grid: {{ color: '#1e1e28' }} }}, y: {{ ticks: {{ color: '#ccc', font: {{ size: 11 }} }}, grid: {{ display: false }} }} }} }}
  }});
}}

function switchTab(name) {{
  document.querySelectorAll('.tab').forEach((t,i) => t.classList.toggle('active', ['competitors','trends','charts'][i] === name));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
}}

buildCards();
buildFilters();
renderCompetitors();
renderTrends();
buildCharts();
</script>
</body>
</html>"""

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard saved to {filename}")


# ----------------------------
# MAIN
# ----------------------------

def main():
    if not API_KEY or API_KEY == "PASTE_YOUR_KEY_HERE":
        print("ERROR: Add your API key to the script or set YOUTUBE_API_KEY env variable.")
        return

    youtube = get_youtube_client()
    all_rows = []

    # Pull competitor channel videos
    print("Pulling competitor channel data...")
    for handle in CHANNELS:
        print(f"  {handle}")
        channel_id, channel_name = resolve_channel_id(youtube, handle)
        if not channel_id:
            continue
        videos = get_recent_videos(youtube, channel_id, channel_name, VIDEOS_PER_CHANNEL)
        print(f"    {len(videos)} videos found")
        all_rows.extend(videos)

    # Pull inspiration channels (trades creators — feeds Trending Trades tab)
    print("Pulling inspiration channel data...")
    for handle in INSPIRATION_CHANNELS:
        print(f"  {handle}")
        channel_id, channel_name = resolve_channel_id(youtube, handle)
        if not channel_id:
            continue
        videos = get_recent_videos(youtube, channel_id, channel_name, VIDEOS_PER_CHANNEL)
        for v in videos:
            v["source"] = f"inspiration: {channel_name}"
        print(f"    {len(videos)} videos found")
        all_rows.extend(videos)

    # Search for trending trades content
    print("\nSearching trades keywords...")
    for keyword in TRADES_KEYWORDS:
        print(f"  '{keyword}'")
        videos = search_trades_content(youtube, keyword, SEARCH_RESULTS_PER_KEYWORD)
        print(f"    {len(videos)} videos found")
        all_rows.extend(videos)

    save_to_csv(all_rows, OUTPUT_FILE)
    build_dashboard(all_rows)
    print("\nDone. Open dashboard.html in your browser.")


if __name__ == "__main__":
    main()

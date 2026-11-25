# BiliFetch

BiliFetch is a cross-platform desktop and CLI video downloader for Bilibili that resolves video, bangumi, collection, and favorite links into local media files (`mp4` or `m4a`).

## Language

### Media & Collections

**Media Target**:
The top-level Bilibili resource identified by a user-supplied URL or ID (a single video `BV`/`av`, a bangumi episode `ep` or season `ss`, a creator collection/series, a favorite folder, or a `b23.tv` short link).
_Avoid_: Link, URL, resource, project

**Bangumi Season**:
An official episodic series on Bilibili (`ss` / `ep`) containing main episodes and optional bonus sections (PVs, trailers, behind-the-scenes clips).
_Avoid_: Anime, show, playlist, drama

**Main Episode**:
A full-length canonical episode belonging to a Bangumi Season's primary storyline (`正片`), deduplicated against short preview clips that share the same episode number.
_Avoid_: Normal video, full clip, standard item

**Extra Clip**:
A supplementary video attached to a Bangumi Season's bonus sections (`花絮 / PV / 二创`), hidden and unchecked by default in the preview list unless explicitly revealed.
_Avoid_: Side video, bonus part, trailer item

**Preview Item**:
A single selectable entry presented in the collection preview list before downloading (either one episode/video in a collection or one part of a single multi-part video).
_Avoid_: Row, entry, video item, node

**Part**:
An individual sub-video segment within a Bilibili video, uniquely identified by a `cid` (Page / 分P). A single video has one or more Parts.
_Avoid_: Page, sub-episode, clip, segment

### Downloading & Streams

**Download Job**:
A single queued unit of work in the download queue tracking state (`wait`, `run`, `merge`, `pause`, `done`, `fail`, `cancel`), resolved Quality Tier, progress, speed, and output path for a selected Preview Item (which may expand into one or more Parts). Pausing a Download Job preserves its on-disk `.part` and `.part.state` chunk progress so resuming continues from the exact byte offset.
_Avoid_: Task, thread, worker, download item

**Quality Tier**:
A Bilibili video resolution and frame-rate profile identified by a `qn` code (e.g., `120` for `4K`, `116` for `1080P60`, `80` for `1080P`, `32` for `480P`). A Download Job has both a requested Quality Tier and an actual resolved Quality Tier returned by Bilibili based on login/VIP entitlement and source availability.
_Avoid_: Resolution, format, bitrate, level

**DASH Stream**:
A pair of separate video and audio media streams (`.v.m4s` and `.a.m4s`) served by Bilibili CDN mirrors that are downloaded in parallel and muxed via `ffmpeg` into the final `.mp4` container (or `.m4a` when audio-only is selected).
_Avoid_: Track, file chunk, segment file

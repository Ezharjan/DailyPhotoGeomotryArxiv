---
layout: default
title: About
nav_order: 4
description: "What Photo Geometry arXiv Daily tracks, how papers are selected, and the research it builds on."
---

# About
{: .no_toc }

Photo Geometry arXiv Daily collects new arXiv papers on **photo geometry** — the geometry of image formation and of recovering cameras and 3D structure from photographs — and organizes them into [research topics]({{ '/topics/' | relative_url }}) that are updated every day.

1. TOC
{:toc}

## Scope

Photo geometry (also called geometric computer vision or multiple-view geometry) covers:

- **Camera models** — the pinhole model and lens distortion, fisheye and omnidirectional cameras, and generalized (non-central) cameras that are described simply as a set of rays.
- **Calibration** — the *intrinsic* parameters (focal length, principal point, skew, distortion) that map rays to pixels, and the *extrinsic* parameters (rotation and translation) that place a camera relative to the world, to other cameras, or to LiDAR, radar and IMU sensors.
- **Geometric relations between views** — epipolar geometry, essential and fundamental matrices, homographies and trifocal tensors, together with the minimal solvers and robust estimators (RANSAC and its descendants) used to estimate them.
- **Pose and reconstruction** — absolute and relative camera pose, structure from motion and bundle adjustment, stereo and multi-view stereo, SLAM and visual odometry, and today's feed-forward models that regress cameras and pointmaps directly from images.
- **Geometry from light and from the Earth's frame** — photometric stereo and shape-from-X, photogrammetry and satellite camera models, and geo-localization of images and cameras.

## Topic design

The topic list follows the classical structure of the field and gives first-class places to two lines of work:

- **Generalized cameras.** An arbitrary imaging system can be described as a set of rays. A network of cameras can then be treated as a *single generalized camera*, with structure-from-motion equations and a generalized epipolar constraint written with rays in Plücker coordinates, and calibrated with generic ray-based methods. → [Generalized & Non-Central Camera Models]({{ '/topics/generalized-cameras.html' | relative_url }}), [Omnidirectional, Fisheye & Panoramic Imaging]({{ '/topics/omnidirectional-cameras.html' | relative_url }})
- **Calibrating cameras with other sensors and with nature.** A camera can be calibrated against a range sensor by observing a planar pattern, and the joint constraint also improves the camera's own calibration. Static outdoor cameras can be geolocated from their image time series, and focal length and scene structure can be recovered from natural cues such as cloud shadows. → [Extrinsic & Multi-Sensor Calibration]({{ '/topics/extrinsic-calibration.html' | relative_url }}), [Camera Calibration & Intrinsics]({{ '/topics/camera-calibration.html' | relative_url }}), [Geo-Localization & Place Recognition]({{ '/topics/geo-localization.html' | relative_url }})

## How papers are selected

1. **Daily query.** Every day at 03:17 UTC a GitHub Actions workflow queries the [arXiv API](https://info.arxiv.org/help/api/index.html) once per topic and requests the newest matching submissions.
2. **Topic definition.** A topic is a set of phrases. Some phrases must appear in the *title*; more specific phrases may appear in the *title or abstract*. Every query is restricted to the arXiv categories cs.CV (Computer Vision and Pattern Recognition), cs.RO (Robotics), cs.GR (Graphics) and eess.IV (Image and Video Processing), including cross-listed papers. Each topic page shows its exact query under "How this topic is matched on arXiv".
3. **Archive.** New papers are merged into a single JSON archive; a paper can belong to several topics. Titles, author lists and comments are cleaned of TeX markup (for example `$360^\circ$` is shown as 360°).
4. **Code links.** A code repository or project page is taken from the paper's arXiv abstract or comments when present. Otherwise the paper is looked up on the [Hugging Face Papers API](https://huggingface.co/papers) (the original Papers with Code service and its API were shut down in July 2025). Recent papers without code are re-checked every Monday.
5. **Website.** Each run rebuilds the pages, but files are committed only when their content changed; GitHub Pages then publishes them.

### Reading the data correctly

- **Dates** are arXiv first-version (v1) submission dates in UTC.
- **Date ranges** ("submitted from … to …") run from the oldest to the newest tracked paper. The archive begins with the first run, which fetches each topic's newest papers (100 by default), so busy topics start later than quiet ones.
- **New papers arrive five days a week.** arXiv announces new submissions Sunday to Thursday at 20:00 US Eastern time, with no announcements on Friday and Saturday (and occasional holiday delays), so the archive normally grows with the runs from Monday to Friday (UTC).
- **"With code"** means that a repository link was found; it does not judge the code.
- **Keyword matching is not peer review.** arXiv's search engine stems words (for example *calibrated* also matches *calibration*), so a topic can occasionally include a tangential paper or miss one that uses unusual wording. The phrases were chosen and tested against the live arXiv API to keep both effects small.

## Data

- [Paper Explorer]({{ '/explorer.html' | relative_url }}) — search every tracked paper by title, author, arXiv ID, venue, topic and code availability.
- [Raw JSON archive]({{ '/photo-geometry-arxiv-daily.json' | relative_url }}) — one record per paper with its arXiv ID, title, up to ten authors and the author count, dates, categories, comment, journal reference, code and project links and topics.

## Credits

- Thank you to [arXiv](https://arxiv.org/) for use of its open access interoperability. Each paper remains subject to the license chosen by its authors on arXiv.
- Code links: [Hugging Face Papers](https://huggingface.co/papers).
- Website theme: [Just the Docs](https://just-the-docs.com/), hosted on GitHub Pages.

The source code is released under the MIT License.{% if site.github.issues_url %} Suggestions for new topics or keywords are welcome as [GitHub issues]({{ site.github.issues_url }}).{% endif %}

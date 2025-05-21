# 🩺 SegDICOM


https://github.com/user-attachments/assets/be56e16b-179f-4687-9430-d32486750810

### Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Prerequisites](#prerequisites)
4. [Installation](#installation)
5. [Project Structure](#project-structure)
6. [Usage](#usage)

   * [Running the Server](#running-the-server)
   * [Web Interface](#web-interface)
   * [API Endpoints](#api-endpoints)
7. [Code Components](#code-components)

   * [VolumeManager](#volumemanager)
   * [Segmentation Dataset Creation](#segmentation-dataset-creation)
   * [Windowing Function](#windowing-function)
8. [Saving Annotations & CSV Log](#saving-annotations--csv-log)
9. [License](#license)

---

## Overview

**SegDICOM** is a web-based application for manual segmentation of DICOM medical images. It allows users to upload DICOM files, navigate slice-by-slice, annotate regions of interest via a brush or erase tool, assign labels, and export segmentation maps in DICOM-SEG format. Annotations are also logged in a CSV for easy tracking and further analysis.

## Features

* Upload multi-frame or single-slice DICOM series
* Slice-by-slice navigation
* Manual brush and eraser tools with adjustable size
* Label management (custom and preset labels)
* Export segmentation as DICOM SEG objects
* Automatic logging of each annotation to `annotations.csv`

## Prerequisites

* Python 3.8+
* pip package manager
* Supported on Windows, Linux, or macOS

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/ayyucedemirbas/segdicom.git
   cd segdicom
   ```
2. Create and activate a virtual environment (optional but recommended):

   ```bash
   python3 -m venv venv
   source venv/bin/activate    # Linux/macOS
   venv\\Scripts\\activate   # Windows
   ```
3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Project Structure

```
segdicom/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── masks/                 # Stored SEG DICOM outputs
├── uploads/               # Temporarily saved uploads
├── templates/
│   └── index.html         # Front-end UI
├── annotations.csv        # Logged annotation metadata
└── LICENSE
```

## Usage

### Running the Server

Start the Flask server in development mode by running:

```bash
python app.py
```

The server listens on `http://0.0.0.0:5000/` by default.

### Web Interface

1. Open `http://localhost:5000/` in your browser.
2. Click **Upload DICOM Files** and select one or more `.dcm` files.
3. Navigate slices with **Previous** and **Next** buttons.
4. Use the **Brush** (🖌️) or **Erase** (🧹) tool to annotate.
5. Adjust brush size with the slider.
6. Enter comma-separated labels or choose presets.
7. Click **Save Mask** (💾) to export segmentation and log to CSV.

### API Endpoints

* `POST /upload` — Upload DICOM files; returns `volume_id` and `num_slices`.
* `GET /slice/<vol_id>/<slice_idx>` — Retrieve pixel data, existing mask, and labels for a specific slice.
* `POST /save_mask/<vol_id>/<slice_idx>` — Save mask data and labels; returns success message.

## Code Components

### VolumeManager

Manages in-memory volumes and masks:

* **add\_volume(file\_paths)**: Reads DICOM files (handles multi-frame), sorts slices, and initializes empty masks.
* **save\_mask(vol\_id, slice\_idx, mask\_data, labels)**: Stores binary mask and labels in memory.
* **get\_mask(vol\_id, slice\_idx)**: Retrieves stored mask and labels.

### Segmentation Dataset Creation

`create_segmentation_ds(ref_dicom, mask_array, labels)`:

* Builds a DICOM SEG object using pydicom's `FileDataset`.
* Sets required metadata (Patient, Study, Series, UIDs).
* Configures segmentation properties (binary mask, algorithm type, labels).
* Embeds the mask as PixelData.

### Windowing Function

`apply_windowing(pixel_array, ds)`:

* Applies DICOM window center/width to pixel intensities.
* Normalizes to 0–255 for display on an HTML5 canvas.

## Saving Annotations & CSV Log

When a mask is saved:

1. Generate a timestamped filename: `seg_<vol_id>_<YYYYmmddHHMMSS>.dcm`.
2. Save the SEG DICOM under `masks/`.
3. Append an entry to `annotations.csv` with:

   * `timestamp`
   * `volume_id`
   * `slice_index`
   * `labels`
   * `dcm_path`

Example CSV row:

```
2025-05-21T14:23:45,1.2.840...,5,"Tumor, Lesion",masks/seg_... .dcm
```

## License

This project is released under the GNU General Public License v3.0. See [LICENSE](LICENSE) for details.



### TODO

- [x] Labeling
- [ ] Add an option to open a folder of .dcm images

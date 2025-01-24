import os
import pydicom
import numpy as np
from flask import Flask, render_template, request, jsonify
from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import generate_uid
import datetime

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MASK_FOLDER'] = 'masks'
app.secret_key = 'supersecretkey'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['MASK_FOLDER'], exist_ok=True)

class VolumeManager:
    def __init__(self):
        self.volumes = {}
    
    def add_volume(self, file_paths):
        vol_id = generate_uid()
        all_slices = []
        
        for file_path in file_paths:
            try:
                ds = pydicom.dcmread(file_path)
                ds.decompress()
                if 'NumberOfFrames' in ds and int(ds.NumberOfFrames) > 1:
                    all_slices.extend(self._split_multiframe(ds))
                else:
                    all_slices.append(ds)
            except Exception as e:
                print(f"Error processing {file_path}: {str(e)}")
                continue

        all_slices = self._sort_slices(all_slices)
        self.volumes[vol_id] = {
            'slices': all_slices,
            'masks': [None] * len(all_slices)
        }
        return vol_id

    def _split_multiframe(self, ds):
        frames = []
        try:
            num_frames = int(ds.NumberOfFrames)
            pixel_array = ds.pixel_array
            for i in range(num_frames):
                frame = ds.copy()
                frame.PixelData = pixel_array[i].tobytes()
                frame.NumberOfFrames = 1
                frame.InstanceNumber = i + 1
                frames.append(frame)
        except Exception as e:
            print(f"Error splitting multiframe: {str(e)}")
            frames = [ds]
        return frames

    def _sort_slices(self, slices):
        try:
            return sorted(slices, key=lambda x: (
                float(x.ImagePositionPatient[2] if 'ImagePositionPatient' in x else 0),
                int(x.InstanceNumber if 'InstanceNumber' in x else 0)
            ))
        except Exception as e:
            print(f"Sorting failed: {str(e)}")
            return slices

    def save_mask(self, vol_id, slice_idx, mask_data):
        if vol_id in self.volumes and 0 <= slice_idx < len(self.volumes[vol_id]['slices']):
            self.volumes[vol_id]['masks'][slice_idx] = mask_data
            return True
        return False

    def get_mask(self, vol_id, slice_idx):
        if vol_id in self.volumes and 0 <= slice_idx < len(self.volumes[vol_id]['masks']):
            return self.volumes[vol_id]['masks'][slice_idx]
        return None

volume_manager = VolumeManager()

def create_segmentation_ds(ref_dicom, mask_array):
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.66.4'
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = '1.2.840.10008.1.2.1'

    ds = FileDataset('segmentation.dcm', {}, file_meta=file_meta, preamble=b"\0"*128)
    
    # Required Patient/Study/Series attributes
    ds.PatientName = ref_dicom.get('PatientName', 'Anonymous')
    ds.PatientID = ref_dicom.get('PatientID', 'Unknown')
    ds.StudyInstanceUID = ref_dicom.get('StudyInstanceUID', generate_uid())
    ds.SeriesInstanceUID = generate_uid()
    ds.FrameOfReferenceUID = ref_dicom.get('FrameOfReferenceUID', generate_uid())

    # Segmentation specific attributes
    ds.Modality = 'SEG'
    ds.SOPClassUID = '1.2.840.10008.5.1.4.1.1.66.4'
    ds.ContentLabel = 'ANNOTATION'
    ds.ContentDescription = 'Manual segmentation'
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = 'MONOCHROME2'
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.LossyImageCompression = '00'
    ds.SegmentationType = 'BINARY'

    # Dimension Organization
    dim_org = Dataset()
    dim_org.DimensionOrganizationUID = generate_uid()
    ds.DimensionOrganizationSequence = [dim_org]

    # Segment Sequence
    segment = Dataset()
    segment.SegmentNumber = 1
    segment.SegmentLabel = 'ManualAnnotation'
    segment.SegmentAlgorithmType = 'MANUAL'
    
    seg_property = Dataset()
    seg_property.CodeValue = 'T-D0050'
    seg_property.CodingSchemeDesignator = 'SRT'
    seg_property.CodeMeaning = 'Tissue'
    segment.SegmentedPropertyCategoryCodeSequence = [seg_property]
    
    ds.SegmentSequence = [segment]

    # Shared Functional Groups
    shared_fg = Dataset()
    pixel_measures = Dataset()
    pixel_measures.PixelSpacing = ref_dicom.get('PixelSpacing', [1.0, 1.0])
    pixel_measures.SliceThickness = ref_dicom.get('SliceThickness', 1.0)
    shared_fg.PixelMeasuresSequence = [pixel_measures]
    ds.SharedFunctionalGroupsSequence = [shared_fg]

    # Per-frame Functional Groups
    frame_fg = Dataset()
    frame_content = Dataset()
    frame_content.DimensionIndexValues = [1, 1]
    frame_fg.FrameContentSequence = [frame_content]
    ds.PerFrameFunctionalGroupsSequence = [frame_fg]

    # Pixel Data
    ds.Rows = ref_dicom.Rows
    ds.Columns = ref_dicom.Columns
    ds.PixelData = mask_array.astype(np.uint8).tobytes()

    return ds

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def handle_upload():
    if 'files[]' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400

    try:
        file_paths = []
        for file in request.files.getlist('files[]'):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)
            file_paths.append(file_path)
        
        vol_id = volume_manager.add_volume(file_paths)
        return jsonify({
            'volume_id': vol_id,
            'num_slices': len(volume_manager.volumes[vol_id]['slices'])
        })
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/slice/<vol_id>/<int:slice_idx>')
def serve_slice(vol_id, slice_idx):
    try:
        volume = volume_manager.volumes.get(vol_id)
        if not volume or slice_idx >= len(volume['slices']):
            return jsonify({'error': 'Invalid slice'}), 404

        ds = volume['slices'][slice_idx]
        pixel_array = apply_windowing(ds.pixel_array, ds)
        
        return jsonify({
            'pixel_data': pixel_array.flatten().tolist(),
            'rows': ds.Rows,
            'columns': ds.Columns,
            'num_frames': len(volume['slices']),
            'mask': volume_manager.get_mask(vol_id, slice_idx)
        })
    except Exception as e:
        print(f"Slice error: {str(e)}")
        return jsonify({'error': 'Failed to process slice'}), 500

@app.route('/save_mask/<vol_id>/<int:slice_idx>', methods=['POST'])
def handle_save_mask(vol_id, slice_idx):
    try:
        volume = volume_manager.volumes.get(vol_id)
        if not volume or slice_idx >= len(volume['slices']):
            return jsonify({'error': 'Invalid volume/slice'}), 404

        mask_data = request.json['mask']
        ref_ds = volume['slices'][slice_idx]
        
        # Validate mask dimensions
        expected_size = ref_ds.Rows * ref_ds.Columns
        if len(mask_data) != expected_size:
            return jsonify({
                'error': f'Mask size mismatch. Expected {expected_size}, got {len(mask_data)}'
            }), 400

        # Convert to numpy array and scale
        mask_array = np.array(mask_data, dtype=np.uint8).reshape(ref_ds.Rows, ref_ds.Columns) * 255

        # Save to memory and disk
        if not volume_manager.save_mask(vol_id, slice_idx, mask_data):
            return jsonify({'error': 'Failed to store mask'}), 500

        seg_ds = create_segmentation_ds(ref_ds, mask_array)
        filename = f"seg_{vol_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.dcm"
        seg_ds.save_as(os.path.join(app.config['MASK_FOLDER'], filename))
        
        return jsonify({'message': 'Mask saved successfully'})
    except Exception as e:
        print(f"Save error: {str(e)}")
        return jsonify({'error': f'Mask save failed: {str(e)}'}), 500

def apply_windowing(pixel_array, ds):
    window_center = ds.get('WindowCenter', np.median(pixel_array))
    window_width = ds.get('WindowWidth', np.ptp(pixel_array))
    
    if isinstance(window_center, pydicom.multival.MultiValue):
        window_center = window_center[0]
        window_width = window_width[0]
    
    min_val = window_center - window_width/2
    max_val = window_center + window_width/2
    
    pixel_array = np.clip(pixel_array, min_val, max_val)
    return ((pixel_array - min_val) / (max_val - min_val) * 255).astype(np.uint8)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
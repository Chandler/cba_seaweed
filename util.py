import rasterio
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as colors
from PIL import Image
import os
import PIL.Image as Image
from PIL import ImageEnhance
import json
from rasterio.mask import mask
from shapely.geometry import shape
import geopandas as gpd
from PIL import Image
from rasterio import MemoryFile
import matplotlib.cm as cm
from matplotlib.colors import Normalize
from matplotlib import pyplot as plt
import numpy as np
from rasterio.io import DatasetReader
from rasterio.transform import Affine
from PIL import ImageDraw, ImageFont

def mkdir(path):
    """
    Make any directories in the path, if they do not already exist.
    """
    if not os.path.exists(path):
        os.makedirs(path)

def load_polygon(path):
    """
    Load a geojson file into a geopandas GeoDataFrame
    """
    with open(path) as f:
        data = json.load(f)
        geoDataFrame = gpd.GeoDataFrame.from_features(data["features"], crs='EPSG:4326')
    return geoDataFrame


def mask_image(image, polygon, crs, transform, crop=True):
    """
    Mask out `image` using `polygon

    Args:
        image: an image to be masked out
        polygon: a lng/lat polygon which should overlap with the image
        crs: the image's reference system
        transform: the images location in the reference system
        crop: whether or not to crop the image to the bounding box
        of the polygon
    """
    polygon = polygon.to_crs(crs)
    
    height, width = image.shape
    metadata = {
        'driver': 'GTiff',
        'dtype': image.dtype,
        'nodata': None,
        'width': width,  
        'height': height, 
        'count': 1, 
        'crs': crs,
        'transform': transform, 
    }
    with MemoryFile() as memfile:
        with memfile.open(**metadata) as ds:
            ds.write(image, indexes=1)
            out_image, out_transform = mask(ds, gdf.geometry.values, crop=crop)
            return out_image[0], out_transform


def write_RGB_geotiff(image, path):
    """ Write a 16bit 3 channel np array as a tif, without location data.
    """
    red, green, blue = image
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with rasterio.open(
        path, 'w', driver='GTiff', 
        height=image.shape[1], count=3, dtype=image.dtype, width=image.shape[2],
        photometric="RGB") as rgb:
        rgb.write(red, 1)
        rgb.write(green, 2)
        rgb.write(blue, 3)

def write_RGB_jpeg(image, path, label=None):
    """ Write a 3 channel 16 bit np array as a normalized 8 bit jpeg with label"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    image_8bit = (image / np.iinfo(image.dtype).max * 255).astype(np.uint8)
    pil_image = Image.fromarray(np.transpose(image_8bit, (1, 2, 0)))

    if label is not None:
        draw = ImageDraw.Draw(pil_image)
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 50) # MacOS
        text_color = (255, 255, 255)  # White color
        text_position = (10, 10)  # Define text position 
        draw.text(text_position, label, font=font, fill=text_color)

    pil_image.save(path, "JPEG")

def compute_snr(object_pixels, surround_pixels):
    """ Compute the signal to noise ratio of the object pixels
    to the surrounding pixels, expressed in decibles.
    """
    # Compute the mean intensities
    mean_signal = np.mean(object_pixels)
    mean_noise = np.mean(surround_pixels)

    # Compute the ratio of signal to noise
    snr = mean_signal / mean_noise

    # Convert the SNR to dB
    snr_db = 10 * np.log10(snr)

    return snr_db

def convert_16bit_to_8_bit(image):
    # to ensure that image data is type of 16-bit integer
    image = image.astype(np.uint16)

    # maximum possible value in 16bit range
    max_val_16bit = np.iinfo(np.uint16).max

    # maximum possible value in 8bit range
    max_val_8bit = np.iinfo(np.uint8).max

    image_8bit = (image / max_val_16bit) * max_val_8bit
    image_8bit = image_8bit.astype(np.uint8)
    return image_8bit
    
def ndvi(R,N):
    """
    Compute NDVI from a 16bit BGRN image.
    """
    # Compute NDVI
    NDVI = (N.astype(float) - R.astype(float)) / (N.astype(float) + R.astype(float))

    NDVI = ((NDVI + 1) / 2) * 65535
    return NDVI.astype(np.uint16)

def color_map(image, vmin=None, vmax=None, cmap=cm.viridis):
    """ Convert a grayscale image into a 3 channel colored mapped
    image for data visualization.
    """
    if vmin is None:
        vmin=np.min(image)

    if vmax is None:
        vmax=np.max(image)

    norm = Normalize(vmin=vmin, vmax=vmax)
    mapper = cm.ScalarMappable(norm=norm, cmap=cmap)
    rgb = (np.array(mapper.to_rgba(image))[..., 0:3] * 255).astype(np.uint8)
    return rgb

def white_balance(rgb_image, white_points, black_points):
    """
    balance an RGB image with a per-channel histogram stretch
    using pre-calculated per-channel white and black points.
    """
    # converting the 16-bit input to float so we can process it
    img_float = rgb_image.astype(float)

    # iterate over each channel
    for cidx in range(3):
        # calculate scale factor for each channel
        scale = 1.0 / (white_points[cidx] - black_points[cidx])
        # apply white balancing to each channel
        img_float[cidx, :, :] = (img_float[cidx, :, :] - black_points[cidx]) * scale

    # converting back to 16 bits
    img_balanced = np.clip(img_float, 0, 1) * 65535.0 # clip values to the valid range
    img_balanced = img_balanced.astype(np.uint16)  # converting to 16 bit integers

    return img_balanced

def white_and_black_points(img_list, white_percentile=95, black_percentile=5):
    """
    for a list of RGB images, compute the global white and black points for
    the entire collection, used for consistant white balancing.
    """
    white_points = []
    black_points = []

    # calculate white and black points for each channel
    for c in range(3):
        top_values = []
        bottom_values = []
        for img in img_list:
            top_1_percentile = np.percentile(img[c, :, :], white_percentile)
            top_values.append(top_1_percentile)
            
            # avoid taking black pixels into account for the black_point calculation
            non_black_pixels = img[c, :, :][img[c, :, :] > 0]
            if len(non_black_pixels) > 0: # check to avoid error if all pixels are black
                bottom_1_percentile = np.percentile(non_black_pixels, black_percentile)
                bottom_values.append(bottom_1_percentile)
        
        white_points.append(np.mean(top_values))
        black_points.append(np.mean(bottom_values) if bottom_values else 0)

    return white_points, black_points


def plot_images(images, labels, ncols, outfile):
    """
    Plot a grid of color images in a grid.

    Args:
        images: a list of arrays required to be plotted.
        labels: a list of strings that are titles of the plots.
        ncols: number of columns in the figure. 
    """
    nrows = np.ceil(len(images) / ncols).astype(int)
    
    fig, axs = plt.subplots(nrows, ncols, figsize=(nrows*5, ncols*5))

    axs = axs.flatten() 

    for i, (img, lbl) in enumerate(zip(images, labels)):
        axs[i].imshow(img)
        axs[i].set_title(lbl)
    
    if len(images) % ncols != 0:  
        for j in range(len(images), nrows * ncols):
            fig.delaxes(axs[j])

    plt.tight_layout()
    plt.savefig(outfile)

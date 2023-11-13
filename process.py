from scene import SceneCollection, SegmentationMask
import util
import numpy as np
import math
import matplotlib.pyplot as plt
from datetime import datetime

def visualize_collection(scene_collection, outdir):
    """
    Write out RGB and NDVI thumbnails for the whole collection
    """
    util.mkdir(outdir)
    
    for scene in scene_collection.scenes:
        # image statistics for white balancing
        wp, _ = util.white_and_black_points([scene.rgb], white_percentile=99.9)

        # crop the scene
        scene = scene.mask_with_poly(scene_collection.area_outline, crop=True)

        # make a visual RGB, hardcode blackpoint to 0
        rgb = scene.balanced_rgb(white_points=wp, black_points=[0,0,0])

        # make an NDVI
        ndvi = scene.colorized_ndvi()

        # stick them together for comparison
        combined = np.concatenate((ndvi, util.convert_16bit_to_8_bit(rgb)), axis=2)

        # write the date onto the final result and save as jpeg
        date = scene.metadata["properties"]["acquired"].split('T')[0]
        util.write_RGB_jpeg(combined, f"{outdir}/ndvi/{scene.name}.ndvi.jpg", label=date)


def visualize_band_descrimination(scene, segmentation_mask, polygon, outdir):
    """
    The goal here is to get a feel for which bands descriminate the
    seaweed object from the surrounding water. A premade segmentation mask is
    required.

    SNR is the ratio of the mean object pixels divided by the mean ocean
    pixels

    The images are also constrast stretched using the object/surround mean value
    which gives a good visual feel for the object/surround seperation
    """

    image = scene.bands
    ndvi = scene.ndvi()

    # add ndvi to the bands
    ndvi = np.expand_dims(ndvi, axis=0)
    image = np.concatenate((image, ndvi), axis=0)

    band_names = scene.band_names + ["ndvi"]

    snrs = []
    thumbnails = []
    object_means = []
    surround_means = []
    
    # Loop over each band and gather some per band artifacts
    for name, band in zip(band_names, image):

        # the masked pixel selection can happen on the full image
        object_pixels = segmentation_mask.object_pixels(band)
        surround_pixels = segmentation_mask.surround_pixels(band)

        # compute SNR
        snr = util.compute_snr(object_pixels, surround_pixels)
        snrs.append(snr)
        print(f"{name} - SNR: {snr}")

        # crop the image before creating the colorized thumbnail
        cropped_image, transform = util.mask_image(
            image=band,
            polygon=polygon,
            crs=scene.dataset.crs,
            transform=scene.dataset.transform
        )
        color_mapped = util.color_map(
            cropped_image,
            vmin=np.min(surround_pixels),
            vmax=np.max(object_pixels)
        )

        thumbnails.append(color_mapped)
        object_means.append(object_pixels.mean())
        surround_means.append(surround_pixels.mean())

    # sort by SNR for the grid output
    combined_list = list(zip(band_names, snrs, thumbnails))
    combined_list.sort(key=lambda x: x[1], reverse=True)

    thumbnails, labels = zip(*[(element[2], f"{element[0]} SNR: {element[1]:.2f}") for element in combined_list])
    util.plot_images(thumbnails, labels, 3, f"{outdir}/band_descrimination_grid.png")

    # Let's also do a time series
    fig, ax = plt.subplots()
    ax.plot(scene.wavelengths, object_means[:-1], label='Object Mean')
    ax.plot(scene.wavelengths, surround_means[:-1], label='Surround Mean')
    ax.legend()

    plt.xlabel('Wavelength')
    plt.ylabel('Mean value')
    plt.title('Time series chart')
    plt.savefig(f"{outdir}/reflectance.png")

project_dir = "/Users/cbabraham/Dropbox/code/seaweed"

scott_lord = SceneCollection.load(
    name="scott_lord",
    captures_dir=f"{project_dir}/data/scott_lord/april_june_2022",
    reference_mask=f"{project_dir}/data/scott_lord/april_june_2022/20220514_150542_32_2480_3B_AnalyticMS_8b_mask.png",
    area_outline=f"{project_dir}/data/scott_lord/area_outline.json",
    reference_scene_id="20220514_150542_32_2480",
)

chandler_cove = SceneCollection.load(
    name="chandler_cove",
    captures_dir=f"{project_dir}/data/chandler_cove/feb_april_2020",
    reference_mask=f"{project_dir}/data/chandler_cove/feb_april_2020/20200316_145828_0e26_3B_AnalyticMS_mask.png",
    area_outline=f"{project_dir}/data/chandler_cove/area_outline.json",
    reference_scene_id="20200316_145828_0e26",
)

aquafort = SceneCollection.load(
    name="aquafort",
    captures_dir=f"{project_dir}/data/aquafort/may_june_2023",
    reference_mask=f"{project_dir}/data/aquafort/may_june_2023/20230518_144318_14_24bf_3B_AnalyticMS_8b_mask.png",
    area_outline=f"{project_dir}/data/aquafort/area_outline.json",
    reference_scene_id="20230518_144318_14_24bf",
)

#--------

def run_projects(scene_collection):
    outdir = f"{project_dir}/output/{scene_collection.name}"
    util.mkdir(outdir)

    visualize_collection(scene_collection, outdir)
    
    visualize_band_descrimination(
        scene_collection.reference_scene,
        scene_collection.reference_mask,
        scene_collection.area_outline,
        outdir
    )

run_projects(aquafort)




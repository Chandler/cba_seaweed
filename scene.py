from rasterio.io import DatasetReader
from dataclasses import dataclass
import os
import json
from datetime import datetime
import rasterio
import util
from typing import Optional
import numpy as np
from rasterio.mask import mask
from rasterio import MemoryFile
from PIL import Image
from abc import ABC, abstractmethod
import geopandas as gpd

@dataclass
class SegmentationMask:
    """ A simple 3 value 8bit segmentation mask
    that can be constructed in photoshop.

    value meanings:

    255 = object
    134 = surround
    0 = ignore
    """
    mask: np.ndarray

    def object_pixels(self, image):
        return image[self.mask == 255]

    def surround_pixels(self, image):
        return image[self.mask == 134]

    @classmethod
    def load(cls, path):
        """ load a png mask, use only the first channel
        """
        img = Image.open(path)
        img_array = np.array(img)[:,:,0]
        return cls(img_array)

@dataclass
class BaseScene(ABC):
    """
    Base class for a multispectral scene, different implementations
    can support different band arrangments such as planet 4 band, planet 8 band.

    Provides helpers for computing common derivative products such as color images
    and NDVI.

    """
    # dict containing data about the scene
    metadata: dict

    # rasterio dataset associated with raster
    dataset: DatasetReader

    # the np arrays containing the values for each band, which are lazy loaded
    # as needed.
    _bands: Optional[np.ndarray] = None

    @property
    @abstractmethod
    def rgb(self):
        pass

    @property
    @abstractmethod
    def bgrn(self):
        pass

    @property
    @abstractmethod
    def band_names(self):
        pass

    @property
    def name(self):
        return self.metadata["id"]

    @property
    def bands(self):
        if self._bands is None:
            print(f"loading {self.name}")
            self._bands = self.dataset.read()
        return self._bands

    def ndvi(self):
        _,_,red,nir = self.bgrn
        return util.ndvi(red, nir)

    def balanced_rgb(self, white_points, black_points):
        """
        Return a colorized RGB array that has been histogram
        normalized using the provided per-channel white and black points
        """
        return util.white_balance(self.rgb, white_points, black_points)

    def colorized_ndvi(self):
        """
        Return a color mapped rgb representation of NDVI
        (as opposed to a single channel grayscale NDVI self.ndvi())
        """
        return util.color_map(self.ndvi()).transpose(2,0,1)

    def mask_with_poly(self, polygon: gpd.GeoDataFrame, crop: bool):
        """
        Given a polygon with lng/lat coordinates, mask out regions of the dataset
        that are outside the polygon and then optionally crop
        the entire raster to the bounding box of the polygon.

        Returns a new masked/cropped instance of BaseScene instead of mutating
        this one.
        """
        
        # convert the polygon from lng/lat to the dataset's reference system
        polygon = polygon.to_crs(self.dataset.crs)
        
        out_image, out_transform = mask(self.dataset,  polygon.geometry.values, crop=crop)
        
        # we have to jump through some hoops to reconstruct the rasterio dataset
        # in memory
        out_meta = self.dataset.meta
        out_meta.update({
            "driver": "GTiff",
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform
        })
        with MemoryFile() as memfile:
            with memfile.open(**out_meta) as ds:
                ds.write(out_image)
                scene = type(self)(self.metadata, ds)
                scene._bands = out_image
                return scene


class SuperDoveScene(BaseScene):
    """
    Implementation of a Scene for Planet's 8 band
    "Superdove"
    """
    band_names = [
      "Coastal Blue",
      "Blue",
      "Green I",
      "Green",
      "Yellow",
      "Red",
      "Red Edge",
      "Near-Infrared",
    ]

    wavelengths = [
        443,
        490,
        531,
        565,
        610,
        665,
        705,
        856
    ]

    @property
    def rgb(self):
        return self.bands[[5, 3, 1], :, :]

    @property
    def bgrn(self):
        return self.bands[[1, 3, 5, 7], :, :]


class Dove4BandScene(BaseScene):
    """
    Implementation of a Scene for Planet's 4 band dove
    """
    band_names = ["Blue", "Green", "Red", "Near-Infrared"]

    @property
    def rgb(self):
        return self.bands[[2, 1, 0], :, :]

    @property
    def bgrn(self):
        return self.bands

class SceneCollection:
    """
    Helper for a collection of Planet scenes.
    """
    def __init__(self, name, scenes, area_outline, reference_index, reference_mask):
        self.name = name
        self.scenes = scenes
        self.area_outline = area_outline
        self.reference_index = reference_index
        self.reference_mask = reference_mask

        print("initialized scene collection")
        for scene in scenes:
            print(scene.metadata["id"])

    @property
    def reference_scene(self):
        return self.scenes[self.reference_index]

    def white_and_black_points(self):
        """ Compute global white and black points for the entire
        collection
        """
        return util.white_and_black_points([scene.rgb for scene in self.scenes])

    @staticmethod
    def parse_planet_directory(captures_dir):
        """ Parse the directory structure included in
        planet orders, returns a list of scene metadatas
        and a map from scene_id to associated tif file.

        This is a bit fragile and only works for Analytic product types.
        """
        metadata = []
        scene_id_to_tif = {}
        for filename in os.listdir(f"{captures_dir}/PSScene"):
            if filename.endswith("metadata.json"):
                print(f"found {filename}")
                with open(f"{captures_dir}/PSScene/{filename}", 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    metadata.append(data)
                    scene_id = data["id"]

                # very ugly way to find the associated tif for each metadata file
                with open(f"{captures_dir}/PSScene/{scene_id}.json", 'r', encoding='utf-8') as f:
                    camera_md = json.load(f)
                    for asset_key in camera_md["assets"].keys():
                        if "tif" in asset_key and "AnalyticMS" in asset_key:
                            tif_file = camera_md["assets"][asset_key]["href"]
                            scene_id_to_tif[scene_id] = tif_file.lstrip("./")

        # sort by aquisition date
        metadata.sort(key=lambda x: datetime.strptime(x['properties']['acquired'], '%Y-%m-%dT%H:%M:%S.%fZ'))
        return metadata, scene_id_to_tif

    @classmethod
    def load(cls, name, captures_dir, reference_mask, area_outline, reference_scene_id):
        """
        SceneCollection constructor that loads data from a planet directory
        
        SceneCollections are initialized with one special reference frame and
        a mask which isolates the area of interest. This mask can be transformed
        from the reference frame to other frames to approximate the region of interest
        in any frame.

        Args:
            name: a name for the collection
            
            captures_dir: a directory full of planet scope scenes
            
            reference_mask: a filepath to a png mask of the reference frame
            
            area_outline: a filepath to a geojson file which contains a polygon
            that roughly outlines the area of interest.

            reference_scene_id: the id of the reference frame
        """
        # look for scene metadata
        metadata, scene_id_to_tif = SceneCollection.parse_planet_directory(captures_dir)

        reference_idx = None

        # load the scenes (lazy, does not load raster into memory)
        scenes = []
        for idx, md in enumerate(metadata):
            scene_id = md["id"]

            if scene_id  == reference_scene_id:
                reference_idx = idx

            ds = rasterio.open(f"{captures_dir}/PSScene/{scene_id_to_tif[scene_id]}")
            
            if ds.count == 8:
                scene = SuperDoveScene(md, ds)
            elif ds.count == 4:
                scene = Dove4BandScene(md, ds)
            else:
                raise ValueError(f"unknown product with {ds.count} bands")
            
            scenes.append(scene)

        if reference_idx is None:
            ids = [s.name for s in scenes]
            raise ValueError(f"reference {reference_scene_id} not found in {ids}")

        return cls(
            name=name,
            scenes=scenes,
            reference_index=reference_idx,
            reference_mask=SegmentationMask.load(reference_mask),
            area_outline=util.load_polygon(area_outline)
        )
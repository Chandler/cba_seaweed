This is a small project to examine some seaweed farms using data from Planet Lab's Dove constellation of multispectral satellites.

# Layout
    `scene.py` a small library for working with planet scenes.
    `util.py` small self contained geo spatial utilities.
    `process.py` visualization code that makes use of the libraries
    `images/` images to embed in the readme
    `data/` not included in repo, contains large planet labs imagery files

The code is factored in a way so that all visualizations can be applied to any farm. The Scene classes factor out the differences between planet 4 and 8 band products so they can be used interchangeably.

code quality note: this was written fairly quickly to balance code quality and results - docstrings, type annotations, comments and general code factoring could all still improve.

# papers I found useful

- [The Utility of Satellites and Autonomous Remote Sensing Platforms for Monitoring Offshore Aquaculture Farms: A Case Study for Canopy Forming Kelps](https://www.frontiersin.org/articles/10.3389/fmars.2020.520223/full)

- [Economic and biophysical limits to seaweed farming for climate change mitigation](https://www.nature.com/articles/s41477-022-01305-9)


# Test Farms
- [aquafort](https://seagrant.unh.edu/blog/2021/12/aquafort-revolutionizing-local-aquaculture-new-hampshire-0):
    - location [43.06897 N, -70.7089] 
    - harvest date: June 6, 2023

- scott_lord_farm:
    - location [43.942709, -69.274238]    
    - harvest date: June 1, 2022

- chandler_cove_farm:
    - location [43.942709, -69.274238]    
    - harvest date: April 17, 2020

# Project
Given that I am new to seaweed science, my goal was to get a brief intuitive and quantitative grasp on what can be learned about seaweed from planet labs 3-5 meter per pixel multi-spectral data.

See the end for the [aquafort](#Aquafort) analysis.

# Results

## setup
A quick look at an RGB frame of scott's farm in photoshop (color corrected and sharpened) shows that the patch is decent sized for this imagery

<img src="./images/scott_crop.png" alt="grid" width="400"/>


The full planet frames are several km across and very large files, a good first step is to grab a quick bounding box of the region from geojson.io and use that to crop the images into something more workable.

(Note, this is not the planet RBG product it is the 8 band multispectral product with the RGB bands extracted and colored corrected. This simple process is a lot quicker and gives you more control than downloading both products)

![full](./images/scott_full_frame.png)

<img src="./images/scott_polygon.png" alt="grid" width="400"/>

## timeseries

Now we can process all of the frames for our duration to see that the size of the patch evolves over time. It's especially visible in NDVI

![farm](./images/scott_farm.gif)

The progression here is hopeful for monitoring seaweed mass throughout its farm lifecycle.

## spectral bands

Although the NDVI looks nice, I wanted to get an understanding of which spectral bands could best discriminate the seaweed from the water.

Several labs have measured kelp spectra 

To do this I took the brightest patch into photoshop and made a quick segmentation mask, white = seaweed, gray = surrounding ocean, black = ignore

<img src="./images/scott_mask.png" alt="grid" width="300"/>

This would be a lot more interesting with automatic segmentation / density estimation but the hand mask will do for now. With it we can compute the signal-to-noise-ratio (SNR) of the object vs the surrounding water for each of the 8 planet spectral bands discrimination

![grid](./images/scott_band_discrimination_grid.png)

Unsurprisingly due to water's absorption of the NIR band, NIR has the highest SNR for our seaweed. Higher than NDVI even, though NDVI would more clearly separate green vegetation from other objects in the water.

Looking at the object/ocean mean values over wavelength we can see the ocean and seaweed don't start to discriminate until around 680nm.

<img src="./images/scott_spectra.png" alt="grid" width="400"/>

for reference lab tests of giant kelp show this reflectance spectrum

<img src="./images/lab_spectra.png" alt="grid" width="400"/>


# Aquafort




import os
import sys
from PIL import Image
import imageio

def create_gif(directory):
    try:
        images = sorted([im for im in os.listdir(directory) if im.endswith(".ndvi.jpg")])
        images_path = [os.path.join(directory, im) for im in images]

        frames = []
        for i in images_path:
            frames.append(imageio.imread(i))

        output_path = os.path.join(directory, "output.gif")
        imageio.mimsave(output_path, frames, 'GIF', duration=500, loop=0)

        print(f'Success: Generated GIF: {output_path}')

    except Exception as error:
        print(f'Error occurred: {error}')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python gif.py directory')
        sys.exit(1)

    input_dir = sys.argv[1]
    if not os.path.isdir(input_dir):
        print(f'Invalid directory: {input_dir}')
        sys.exit(1)

    create_gif(input_dir)
